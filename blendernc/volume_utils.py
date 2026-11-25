"""Helpers for the Datacube Volume node: layout, placement and VDB files.

A 3-D or 4-D variable becomes a Blender Volume object read from OpenVDB
files written with the ``openvdb`` module that ships with Blender. The
horizontal dimensions become the voxel x and y axes, the remaining spatial
dimension becomes the vertical axis, and an optional "animate" dimension is
spread over frames:

* ``(x, y, z)`` gives a static volume;
* ``(x, y, time)`` gives a static space-time cube, time running upwards;
* ``(x, y, z, time)`` gives a volume animated along time.

Voxels sit on the coordinates (see :class:`Placement`): evenly spaced ones
set the voxel size directly, descending ones are flipped, and unevenly
spaced or curvilinear ones are resampled onto a regular grid by nearest
neighbour, which the node tells the user about.

Blender caches VDB grids by file path for the whole session, so a file that
is rewritten in place is never read again. Every bake therefore writes its
files under a new token (see :func:`vdb_stem`), and the current-frame mode
writes one file per frame index instead of reusing a single path.

When the tree changes but the coordinates do not (same
:func:`placement_key`), a bake only refreshes the values and reuses the
last placement. The user's move, rotation and scale of the object are kept
on top of the placement, whatever the bake (see :func:`place_object`).

Pure helpers raise ``ValueError`` with a two-line message (problem, then
what to do); the operator turns it into a report.
"""

import glob
import logging
import os
import shutil

import bpy
import numpy as np
from mathutils import Vector

from .core.fields import RANGE_PROPERTIES
from .core.volume import (
    ANIMATE_AUTO,
    ANIMATE_NONE,
    clamp_frame,
    finite_range,
    frame_array,
    frame_count,
    placement_key,
    volume_layout,
    volume_placement,
)
from .utils import get_data_from_datastruct, get_dataset, keep_enum_items, range_locked

logger = logging.getLogger(__name__)


# Values of the node's ``frame_mode`` enum.
FRAMES_SEQUENCE = "SEQUENCE"
FRAMES_LIVE = "LIVE"

# Default directory for the VDB files, relative to the .blend file.
DEFAULT_VDB_DIR = "//blendernc_vdb/"


# Shown on the node when the files are written to Blender's temporary folder.
UNSAVED_WARNING = (
    "Unsaved .blend file: the VDB files are temporary"
    "\nand deleted on quit. Save the file and bake again."
)


# --------------------------------------------------------------------------
# Layout
# --------------------------------------------------------------------------


_ANIMATE_FIXED_ITEMS = [
    (ANIMATE_AUTO, "Auto", "Animate the time dimension of a 4D field only", 0),
    (ANIMATE_NONE, "None (static)", "Build one static volume", 1),
]


@keep_enum_items
def get_animate_dims(node, context):
    """Enum items callback: "Auto", "None" and the linked variable's dims.

    The dims are those left after the tree's slicing, so a dimension
    dropped by a Select node is not offered. The two fixed entries come
    first so their stored index never changes when another variable, with
    other dimensions, is linked.
    """
    items = list(_ANIMATE_FIXED_ITEMS)
    socket = node.inputs.get("Variable")
    datastruct = node.BNC_datastructs[0] if node.BNC_datastructs else None
    dataset = get_dataset(datastruct) if datastruct is not None else None
    variable = socket.default_value if socket else ""
    if dataset is not None and variable in dataset:
        data = get_data_from_datastruct(datastruct, variable, fill=False)
        for index, dim in enumerate(data.dims, start=len(items)):
            items.append((dim, dim, f"Animate along {dim}", index))
    return items


def bake_range(obj, data):
    """Range written on the volume: the stored one under "Lock range".

    With the scene's "Lock range" setting on and a range already stored on
    ``obj``, that range is kept, so the colour scale stays fixed and the
    whole variable is not read again; otherwise it is computed from
    ``data``.
    """
    if range_locked() and all(key in obj for key in RANGE_PROPERTIES):
        low, high = RANGE_PROPERTIES
        return float(obj[low]), float(obj[high])
    return finite_range(data)


# --------------------------------------------------------------------------
# Placement
# --------------------------------------------------------------------------


# Placement of the last bake per node, reused by the current-frame mode and
# by a refresh of the values, so a curvilinear grid is not matched again on
# every frame or variable. Keyed by the node's pointer; the node's
# ``baked_placement`` key tells a stale entry.
_PLACEMENTS = {}


def _cached_placement(node, data, layout):
    """Placement of the node's last bake, computed again when it is stale."""
    cached = _PLACEMENTS.get(node.as_pointer())
    if cached is not None and cached[0] == node.baked_placement:
        return cached[1]
    placement = volume_placement(data, layout)
    _PLACEMENTS[node.as_pointer()] = (node.baked_placement, placement)
    return placement


def _keeps_placement(node, key):
    """True when the node's last object is still its target and ``key`` matches.

    The object must exist: a new one has no transform worth keeping.
    """
    baked = bpy.data.objects.get(node.baked_object) if node.baked_object else None
    return (
        baked is not None
        and node.baked_object == node.volume_obj_name
        and key == node.baked_placement
    )


# --------------------------------------------------------------------------
# Files
# --------------------------------------------------------------------------


def _vdb_base(node):
    """Base folder for the node's files, and whether it is a temporary one.

    The node's ``vdb_dir`` may be relative to the .blend file (``//``); in
    an unsaved file such a path falls back to Blender's temporary folder,
    which Blender deletes on quit.
    """
    base = node.vdb_dir or DEFAULT_VDB_DIR
    if base.startswith("//") and not bpy.data.filepath:
        return bpy.app.tempdir, True
    return bpy.path.abspath(base), False


def vdb_directory(node, create=True):
    """Absolute directory holding the VDB files of ``node``.

    Each node writes into its own sub-directory, so cleaning up stale files
    never touches another node's files.

    Parameters
    ----------
    node : DatacubeVolume
        Node whose folder is wanted.
    create : bool, optional
        Create the directory when missing, by default ``True``.
    """
    base, _ = _vdb_base(node)
    folder = bpy.path.clean_name(f"{node.id_data.name}_{node.name}")
    directory = os.path.join(base, folder)
    if create:
        os.makedirs(directory, exist_ok=True)
    return directory


def vdb_stem(variable, token):
    """File name stem shared by all frames of one bake."""
    return f"{bpy.path.clean_name(variable)}_{token}"


def frame_path(directory, stem, index):
    """Path of frame ``index``; Blender numbers sequence files from 1."""
    return os.path.join(directory, f"{stem}_{index + 1:04d}.vdb")


def remove_vdb_files(directory, keep=()):
    """Delete the ``.vdb`` files in ``directory`` except the paths in ``keep``."""
    for path in glob.glob(os.path.join(directory, "*.vdb")):
        if path not in keep:
            os.remove(path)


def _same_folder(path, directory):
    """True when ``path`` lies directly in ``directory``."""
    folder = os.path.normcase(os.path.normpath(os.path.dirname(path)))
    return folder == os.path.normcase(os.path.normpath(directory))


def release_vdb_directory(node):
    """Delete the node's VDB folder unless a Volume still reads from it.

    Called when the node is deleted. The Volume object it baked usually
    stays in the scene and keeps its files; once no Volume datablock points
    into the folder, nothing needs it any more.

    Returns
    -------
    bool
        ``True`` when the folder was removed.
    """
    _PLACEMENTS.pop(node.as_pointer(), None)
    directory = vdb_directory(node, create=False)
    if not os.path.isdir(directory):
        return False
    for volume in bpy.data.volumes:
        path = bpy.path.abspath(volume.filepath, library=volume.library)
        if volume.filepath and _same_folder(path, directory):
            logger.info(f"{node.name}: kept {directory}, {volume.name} reads it")
            return False
    shutil.rmtree(directory, ignore_errors=True)
    logger.info(f"{node.name}: removed {directory}")
    return True


def write_vdb(path, array, grid_name, background=0.0):
    """Write a 3-D array to ``path`` as a float grid called ``grid_name``.

    Voxels equal to ``background`` stay inactive, which keeps the file small
    and lets missing data (filled with the same value) render as empty.
    """
    import openvdb

    grid = openvdb.FloatGrid()
    grid.background = float(background)
    grid.copyFromArray(array)
    grid.name = grid_name
    openvdb.write(path, grids=[grid])


# --------------------------------------------------------------------------
# Blender objects
# --------------------------------------------------------------------------


def look_up_volume_object(object_name):
    """Return the Volume object called ``object_name``, creating what is missing.

    Raises
    ------
    ValueError
        If ``object_name`` belongs to an object that is not a volume.
    """
    obj = bpy.data.objects.get(object_name)
    if obj is not None and obj.type != "VOLUME":
        raise ValueError(
            f"{object_name} is not a volume ({obj.type.lower()})."
            "\nChoose another volume name."
        )
    if obj is None:
        volume = bpy.data.volumes.get(object_name)
        if volume is None or volume.users:
            volume = bpy.data.volumes.new(object_name)
        obj = bpy.data.objects.new(object_name, volume)
    if not obj.users_collection:
        bpy.context.collection.objects.link(obj)
    return obj


def _placed_here(obj, node):
    """True when ``node`` placed ``obj`` before, so it has a user transform."""
    return obj.name == node.baked_object and min(node.placed_scale) > 0


def place_object(obj, node, location, scale):
    """Put ``obj`` on a placement, keeping the user's transform on top of it.

    ``node.placed_location`` and ``node.placed_scale`` hold the placement
    applied last; whatever the user did since (move, rotate, scale) is
    their transform. It is kept: the object is shifted by the change of
    origin, counted in voxels of the last placement along the object's own
    axes, and its scale is multiplied by the change of voxel size. With the
    same placement nothing moves; after a Slice, the slice lands where that
    part of the volume was. An object this node never placed (new, or baked
    before placements were recorded) gets the placement itself.

    Parameters
    ----------
    obj : bpy.types.Object
        The Volume object.
    node : DatacubeVolume
        The node baking it; its ``placed_*`` properties are updated.
    location, scale : sequence of float
        The new placement, vertical scale included.
    """
    # Compared in single precision, as stored: an unchanged placement is a
    # shift of exactly zero and a ratio of exactly one.
    location = np.asarray(location, dtype=np.float32)
    scale = np.asarray(scale, dtype=np.float32)
    if _placed_here(obj, node):
        last_location = np.asarray(node.placed_location, dtype=np.float32)
        last_scale = np.asarray(node.placed_scale, dtype=np.float32)
        voxels = Vector((location - last_location) / last_scale)
        obj.location += obj.matrix_basis.to_3x3() @ voxels
        obj.scale = [old * ratio for old, ratio in zip(obj.scale, scale / last_scale)]
    else:
        obj.location, obj.scale = location.tolist(), scale.tolist()
    node.placed_location, node.placed_scale = location.tolist(), scale.tolist()


def stretch_vertically(obj, node):
    """Apply the node's vertical scale to ``obj``, keeping the user's transform."""
    if _placed_here(obj, node):
        location, scale = list(node.placed_location), list(node.placed_scale)
    else:  # baked before placements were recorded: only Z is known
        location, scale = list(obj.location), list(obj.scale)
    location[2] = node.baked_z_origin * node.vertical_scale
    scale[2] = node.baked_z_step * node.vertical_scale
    place_object(obj, node, location, scale)


def point_volume_at(volume, path, frames=1):
    """Read ``volume`` from ``path``, as a sequence of ``frames`` files if > 1.

    A sequence starts at frame 0 and holds its last file afterwards, the
    same clamping the animated textures use.
    """
    _set_filepath(volume, path)
    volume.is_sequence = frames > 1
    if frames > 1:
        volume.frame_start = 0
        volume.frame_offset = 0
        volume.frame_duration = frames
        volume.sequence_mode = "EXTEND"


def write_object_range(obj, value_range):
    """Store the field range on ``obj`` for the material's Map Range node."""
    for key, value in zip(RANGE_PROPERTIES, value_range):
        obj[key] = value


# --------------------------------------------------------------------------
# Node pipeline
# --------------------------------------------------------------------------


def volume_data(node):
    """Return ``(variable, data, layout)`` for a Datacube Volume node.

    ``data`` keeps NaN for missing values; the slicing of the tree applies.

    Raises
    ------
    ValueError
        If no variable is linked, it is not in the dataset, or its
        dimensions cannot form a volume.
    """
    variable = node.inputs["Variable"].default_value
    dataset = get_dataset(node.BNC_datastructs[0])
    if not variable or dataset is None:
        raise ValueError("No variable is linked.\nLink a Datacube Variable output.")
    if variable not in dataset:
        raise ValueError(f"{variable} is not in the datacube.\nLink another variable.")
    data = get_data_from_datastruct(node.BNC_datastructs[0], variable, fill=False)
    return variable, data, volume_layout(data, node.animate_dim)


def _set_filepath(volume, path):
    """Point ``volume`` at ``path``, relative to the .blend file when saved."""
    if bpy.data.filepath:
        try:
            path = bpy.path.relpath(path)
        except ValueError:  # another drive on Windows
            pass
    volume.filepath = path


def bake_volume(node, scene, keep_placement=False):
    """Write the VDB files of ``node`` and return the Volume object.

    Everything that can fail is checked before files or objects change.
    Every frame is written in sequence mode; in current-frame mode only the
    frame of ``scene`` is, and :func:`write_live_frame` follows playback.

    With ``keep_placement``, a bake on the coordinates of the last one (same
    :func:`placement_key`, same object) only refreshes the values and reuses
    the last placement. Either way, :func:`place_object` keeps the user's
    transform of an existing object on top of the placement.

    Returns
    -------
    tuple
        ``(obj, notes, refreshed)``: the Volume object, the messages for
        the user as ``{"INFO": [...], "WARNING": [...]}``, and whether only
        the values were refreshed. Info notes say what was resampled; the
        warning says the files are temporary.

    Raises
    ------
    ValueError
        With the message shown on the node.
    """
    variable, data, layout = volume_data(node)
    key = placement_key(data, layout)
    refresh = keep_placement and _keeps_placement(node, key)
    if refresh:
        placement = _cached_placement(node, data, layout)
    else:
        placement = volume_placement(data, layout)
    frames = frame_count(data, layout)
    obj = look_up_volume_object(node.volume_obj_name)
    value_range = bake_range(obj, data)

    node.bake_token += 1  # new file names, so Blender's grid cache misses
    node.baked_placement = key
    _PLACEMENTS[node.as_pointer()] = (key, placement)
    directory = vdb_directory(node)
    stem = vdb_stem(variable, node.bake_token)
    remove_vdb_files(directory)
    live = node.frame_mode == FRAMES_LIVE and frames > 1
    indices = [clamp_frame(scene.frame_current, frames)] if live else range(frames)
    background = value_range[0]
    for index in indices:
        array = frame_array(data, layout, index, background, placement)
        write_vdb(frame_path(directory, stem, index), array, variable, background)

    point_volume_at(
        obj.data, frame_path(directory, stem, indices[0]), 1 if live else frames
    )
    place_object(obj, node, *placement.transform(node.vertical_scale))
    node.baked_z_origin, node.baked_z_step = placement.origin[2], placement.step[2]
    write_object_range(obj, value_range)
    logger.info(
        f"{node.name}: wrote {len(indices)} VDB file(s) of {variable} "
        f"({', '.join(filter(None, layout))}) to {directory}"
        f"{', same placement' if refresh else ''}"
    )
    temporary = _vdb_base(node)[1]
    notes = {
        "INFO": list(placement.notes),
        "WARNING": [UNSAVED_WARNING] if temporary else [],
    }
    return obj, notes, refresh


def _live_target(node):
    """Return ``(obj, variable, data, layout)`` of an animated baked volume.

    ``None`` when the node has no baked Volume object, its variable cannot
    form a volume any more, or nothing is animated.
    """
    obj = bpy.data.objects.get(node.baked_object) if node.baked_object else None
    if obj is None or obj.type != "VOLUME":
        return None
    try:
        variable, data, layout = volume_data(node)
    except ValueError:
        return None
    if frame_count(data, layout) < 2:
        return None
    return obj, variable, data, layout


def write_live_frame(node, frame):
    """Show frame ``frame`` on the volume of a node in current-frame mode.

    The frame's file is written when missing and the volume is pointed at
    it; the files of other frames are removed. Returns ``True`` when the
    volume changed. Half-connected or invalid nodes are skipped silently,
    so playback never breaks.
    """
    target = _live_target(node)
    if target is None:
        return False
    obj, variable, data, layout = target
    index = clamp_frame(frame, frame_count(data, layout))
    directory = vdb_directory(node)
    path = frame_path(directory, vdb_stem(variable, node.bake_token), index)
    if bpy.path.abspath(obj.data.filepath) == path and os.path.exists(path):
        return False
    if not os.path.exists(path):
        background = obj.get(RANGE_PROPERTIES[0], 0.0)
        placement = _cached_placement(node, data, layout)
        array = frame_array(data, layout, index, background, placement)
        write_vdb(path, array, variable, background)
    remove_vdb_files(directory, keep=(path,))
    _set_filepath(obj.data, path)
    return True
