"""Helpers for the Datacube Volume node: layout, voxel transform and VDB files.

A 3-D or 4-D variable becomes a Blender Volume object read from OpenVDB
files written with the ``openvdb`` module that ships with Blender. The
horizontal dimensions become the voxel x and y axes, the remaining spatial
dimension becomes the vertical axis, and an optional "animate" dimension is
spread over frames:

* ``(x, y, z)`` gives a static volume;
* ``(x, y, time)`` gives a static space-time cube, time running upwards;
* ``(x, y, z, time)`` gives a volume animated along time.

Blender caches VDB grids by file path for the whole session, so a file that
is rewritten in place is never read again. Every bake therefore writes its
files under a new token (see :func:`vdb_stem`), and the current-frame mode
writes one file per frame index instead of reusing a single path.

Pure helpers raise ``ValueError`` with a two-line message (problem, then
what to do); the operator turns it into a report.
"""

import glob
import logging
import os
import re

import bpy
import numpy as np

from .utils import (
    RANGE_PROPERTIES,
    get_data_from_datastruct,
    get_dataset,
    get_surface_dims,
    keep_enum_items,
)

logger = logging.getLogger(__name__)

# Values of the node's ``animate_dim`` enum that are not dimension names.
ANIMATE_AUTO = "AUTO"
ANIMATE_NONE = "NONE"

# Values of the node's ``frame_mode`` enum.
FRAMES_SEQUENCE = "SEQUENCE"
FRAMES_LIVE = "LIVE"

# Default directory for the VDB files, relative to the .blend file.
DEFAULT_VDB_DIR = "//blendernc_vdb/"

# Relative spacing error tolerated before a coordinate counts as uneven.
SPACING_RTOL = 1e-3

_X_NAME = re.compile(r"(^|[^a-z])(x|lon)")
_Y_NAME = re.compile(r"(^|[^a-z])(y|lat)")


# --------------------------------------------------------------------------
# Layout
# --------------------------------------------------------------------------


def time_dims(data):
    """Dimensions of ``data`` whose coordinate holds ``datetime64`` values."""
    return [
        dim
        for dim in data.dims
        if dim in data.coords and np.issubdtype(data[dim].dtype, np.datetime64)
    ]


def default_animate_dim(data):
    """Dimension animated when the node is set to "Auto", or ``""``.

    A 4-D field is animated along its time dimension (or, without one, its
    first dimension, where CF files keep time). A 3-D field is not animated,
    so ``(x, y, time)`` becomes a space-time cube.
    """
    if len(data.dims) != 4:
        return ""
    times = time_dims(data)
    return times[0] if times else data.dims[0]


_ANIMATE_FIXED_ITEMS = [
    (ANIMATE_AUTO, "Auto", "Animate the time dimension of a 4D field only", 0),
    (ANIMATE_NONE, "None (static)", "Build one static volume", 1),
]


@keep_enum_items
def get_animate_dims(node, context):
    """Enum items callback: "Auto", "None" and the linked variable's dims.

    The two fixed entries come first so their stored index never changes
    when another variable, with other dimensions, is linked.
    """
    items = list(_ANIMATE_FIXED_ITEMS)
    socket = node.inputs.get("Variable")
    dataset = get_dataset(node.BNC_datastructs[0]) if node.BNC_datastructs else None
    variable = socket.default_value if socket else ""
    if dataset is not None and variable in dataset:
        for index, dim in enumerate(dataset[variable].dims, start=len(items)):
            items.append((dim, dim, f"Animate along {dim}", index))
    return items


def resolve_animate_dim(data, choice):
    """Turn the node's ``animate_dim`` value into a dimension name or ``""``.

    Raises
    ------
    ValueError
        If ``choice`` names a dimension ``data`` does not have.
    """
    if choice == ANIMATE_AUTO:
        return default_animate_dim(data)
    if choice in ("", ANIMATE_NONE):
        return ""
    if choice not in data.dims:
        dims = ", ".join(map(str, data.dims))
        raise ValueError(
            f"{data.name} has no dimension {choice!r} ({dims})."
            "\nPick another dimension in Animate along."
        )
    return choice


def _horizontal_pair(data, spatial):
    """Return ``(x_dim, y_dim)`` among the spatial dims of ``data``.

    Surface dimensions are taken from :func:`get_surface_dims` when exactly
    two of them are spatial; otherwise the last two spatial dimensions are
    used, the CF ``(..., lat, lon)`` order. Within the pair, names that look
    like x/lon or y/lat decide; failing that the last one is x.
    """
    surface = [dim for dim in get_surface_dims(data.to_dataset()) if dim in spatial]
    if len(surface) != 2:
        logger.info(f"{data.name}: no surface dimensions found, using the last two")
        surface = spatial[-2:]
    first, second = surface
    if _X_NAME.search(first.lower()) and not _X_NAME.search(second.lower()):
        return first, second
    if _Y_NAME.search(second.lower()) and not _Y_NAME.search(first.lower()):
        return first, second
    return second, first


def volume_layout(data, animate_choice):
    """Assign the dimensions of ``data`` to the volume axes.

    Parameters
    ----------
    data : xarray.DataArray
        Variable with its slicing already applied.
    animate_choice : str
        Value of the node's ``animate_dim`` enum.

    Returns
    -------
    tuple
        ``(x_dim, y_dim, vertical_dim, animate_dim)``. ``vertical_dim`` is
        ``""`` for an animated 2-D slab and ``animate_dim`` is ``""`` for a
        static volume.

    Raises
    ------
    ValueError
        If the field has too few or too many dimensions for a volume.
    """
    ndim = len(data.dims)
    dims = ", ".join(map(str, data.dims))
    problem = f"{data.name} is {ndim}D ({dims})."
    if ndim < 3:
        raise ValueError(problem + "\nA volume needs a 3D field; use Datacube Texture.")
    if ndim > 4:
        raise ValueError(
            problem + "\nUse a Datacube Select node to pick a slice first."
        )
    animate = resolve_animate_dim(data, animate_choice)
    spatial = [dim for dim in data.dims if dim != animate]
    if len(spatial) > 3:
        raise ValueError(
            problem + "\nPick a dimension in Animate along, or select a level first."
        )
    x_dim, y_dim = _horizontal_pair(data, spatial)
    rest = [dim for dim in spatial if dim not in (x_dim, y_dim)]
    return x_dim, y_dim, (rest[0] if rest else ""), animate


def frame_count(data, layout):
    """Number of frames of the layout: the animate size, or 1 when static."""
    animate = layout[3]
    return data.sizes[animate] if animate else 1


def frame_array(data, layout, index=None, background=0.0):
    """Return one frame of ``data`` as a ``(x, y, vertical)`` float32 array.

    Parameters
    ----------
    data : xarray.DataArray
        Variable with its slicing applied; missing values may be NaN.
    layout : tuple
        As returned by :func:`volume_layout`.
    index : int, optional
        Position along the animate dimension; ignored when static.
    background : float, optional
        Value given to missing data, so it becomes inactive voxels.
    """
    x_dim, y_dim, vertical, animate = layout
    if animate:
        data = data.isel({animate: index or 0})
    if vertical:
        values = data.transpose(x_dim, y_dim, vertical).values
    else:
        values = data.transpose(x_dim, y_dim).values[..., np.newaxis]
    values = np.nan_to_num(values.astype(np.float32), nan=background)
    return np.ascontiguousarray(values)


def finite_range(data):
    """Return ``(min, max)`` of the finite values of ``data``, ``(0, 0)`` if none."""
    low, high = float(data.min(skipna=True)), float(data.max(skipna=True))
    if not (np.isfinite(low) and np.isfinite(high)):
        return 0.0, 0.0
    return low, high


# --------------------------------------------------------------------------
# Transform
# --------------------------------------------------------------------------


def axis_spacing(values):
    """Return ``(origin, step)`` of evenly spaced 1-D numeric ``values``.

    Uneven, non-numeric or single-valued coordinates give ``None``.
    """
    values = np.asarray(values)
    if (
        values.ndim != 1
        or values.size < 2
        or not np.issubdtype(values.dtype, np.number)
    ):
        return None
    steps = np.diff(values.astype(np.float64))
    step = steps.mean()
    if step == 0 or not np.allclose(steps, step, rtol=SPACING_RTOL, atol=0):
        return None
    return float(values[0]), float(step)


def voxel_transform(coords, layout, vertical_scale=1.0):
    """Object ``(location, scale)`` that places voxels on the coordinates.

    Parameters
    ----------
    coords : dict
        Mapping of the x and y dimension names to their (sliced) coordinate
        values, so the volume overlays a Datacube Grid baked from them.
    layout : tuple
        As returned by :func:`volume_layout`.
    vertical_scale : float, optional
        Height of one voxel along the vertical axis.

    Returns
    -------
    tuple
        ``((x0, y0, 0.0), (dx, dy, vertical_scale))``. An axis whose
        coordinate is uneven or curvilinear falls back to index space.
    """
    location, scale = [0.0, 0.0, 0.0], [1.0, 1.0, vertical_scale]
    for axis, dim in enumerate(layout[:2]):
        spacing = axis_spacing(coords.get(dim, ()))
        if spacing is None:
            logger.info(f"{dim} is not evenly spaced; using index space")
            continue
        location[axis], scale[axis] = spacing
    return tuple(location), tuple(scale)


# --------------------------------------------------------------------------
# Files
# --------------------------------------------------------------------------


def vdb_directory(node):
    """Absolute directory holding the VDB files of ``node``, created if needed.

    The node's ``vdb_dir`` may be relative to the .blend file (``//``); in an
    unsaved file such a path falls back to Blender's temporary directory.
    Each node writes into its own sub-directory, so cleaning up stale files
    never touches another node's files.
    """
    base = node.vdb_dir or DEFAULT_VDB_DIR
    if base.startswith("//") and not bpy.data.filepath:
        logger.warning(
            f"{node.name}: the .blend file is not saved; writing VDB files to "
            f"{bpy.app.tempdir}"
        )
        base = bpy.app.tempdir
    folder = bpy.path.clean_name(f"{node.id_data.name}_{node.name}")
    directory = os.path.join(bpy.path.abspath(base), folder)
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


def clamp_frame(frame, frames):
    """Frame index used at scene frame ``frame`` for ``frames`` frames."""
    return min(max(frame, 0), frames - 1)


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


def axis_coords(datastruct, layout):
    """Sliced coordinate values of the x and y dimensions of ``layout``."""
    return {
        dim: get_data_from_datastruct(datastruct, dim, fill=False).values
        for dim in layout[:2]
    }


def _set_filepath(volume, path):
    """Point ``volume`` at ``path``, relative to the .blend file when saved."""
    if bpy.data.filepath:
        try:
            path = bpy.path.relpath(path)
        except ValueError:  # another drive on Windows
            pass
    volume.filepath = path


def bake_volume(node, scene):
    """Write the VDB files of ``node`` and return the Volume object.

    Everything that can fail is checked before files or objects change.
    Every frame is written in sequence mode; in current-frame mode only the
    frame of ``scene`` is, and :func:`write_live_frame` follows playback.

    Raises
    ------
    ValueError
        With the message shown on the node.
    """
    variable, data, layout = volume_data(node)
    coords = axis_coords(node.BNC_datastructs[0], layout)
    location, scale = voxel_transform(coords, layout, node.vertical_scale)
    value_range = finite_range(data)
    frames = frame_count(data, layout)
    obj = look_up_volume_object(node.volume_obj_name)

    node.bake_token += 1  # new file names, so Blender's grid cache misses
    directory = vdb_directory(node)
    stem = vdb_stem(variable, node.bake_token)
    remove_vdb_files(directory)
    live = node.frame_mode == FRAMES_LIVE and frames > 1
    indices = [clamp_frame(scene.frame_current, frames)] if live else range(frames)
    for index in indices:
        array = frame_array(data, layout, index, background=value_range[0])
        write_vdb(frame_path(directory, stem, index), array, variable, value_range[0])

    point_volume_at(
        obj.data, frame_path(directory, stem, indices[0]), 1 if live else frames
    )
    obj.location, obj.scale = location, scale
    write_object_range(obj, value_range)
    logger.info(
        f"{node.name}: wrote {len(indices)} VDB file(s) of {variable} "
        f"({', '.join(filter(None, layout))}) to {directory}"
    )
    return obj


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
        write_vdb(
            path, frame_array(data, layout, index, background), variable, background
        )
    remove_vdb_files(directory, keep=(path,))
    _set_filepath(obj.data, path)
    return True
