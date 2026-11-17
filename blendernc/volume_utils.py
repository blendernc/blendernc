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

Pure helpers raise ``ValueError`` with a two-line message (problem, then
what to do); the operator turns it into a report.
"""

import glob
import logging
import os
import re
import shutil
from dataclasses import dataclass, field

import bpy
import numpy as np

from .utils import (
    RANGE_PROPERTIES,
    get_data_from_datastruct,
    get_dataset,
    get_surface_dims,
    keep_enum_items,
    range_locked,
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

# A voxel column of a resampled curvilinear grid stays empty when its
# nearest source point is further away than this fraction of the source's
# local spacing (the distance to the furthest of its four nearest points).
CURVILINEAR_REACH = 0.75

# Shown on the node when the files are written to Blender's temporary folder.
UNSAVED_WARNING = (
    "Unsaved .blend file: the VDB files are temporary"
    "\nand deleted on quit. Save the file and bake again."
)

_X_NAME = re.compile(r"(^|[^a-z])(x|lon)")
_Y_NAME = re.compile(r"(^|[^a-z])(y|lat)")

# CF attributes that mark a horizontal coordinate, besides its name.
_X_STANDARD_NAMES = {"longitude", "grid_longitude", "projection_x_coordinate"}
_Y_STANDARD_NAMES = {"latitude", "grid_latitude", "projection_y_coordinate"}
_X_UNITS = {"degrees_east", "degree_east", "degrees_e", "degree_e"}
_Y_UNITS = {"degrees_north", "degree_north", "degrees_n", "degree_n"}


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


def _is_x_coord(name, coord):
    """True when a coordinate looks like x or longitude, by name or CF attrs."""
    attrs = coord.attrs
    return (
        bool(_X_NAME.search(name.lower()))
        or attrs.get("standard_name") in _X_STANDARD_NAMES
        or str(attrs.get("units", "")).lower() in _X_UNITS
    )


def _is_y_coord(name, coord):
    """True when a coordinate looks like y or latitude, by name or CF attrs."""
    attrs = coord.attrs
    return (
        bool(_Y_NAME.search(name.lower()))
        or attrs.get("standard_name") in _Y_STANDARD_NAMES
        or str(attrs.get("units", "")).lower() in _Y_UNITS
    )


def _coords_2d(data, dims):
    """Numeric 2-D coordinates of ``data`` spanning exactly ``dims``."""
    return {
        name: coord
        for name, coord in data.coords.items()
        if coord.ndim == 2
        and set(coord.dims) == set(dims)
        and np.issubdtype(coord.dtype, np.number)
    }


def _varies_most_along(coord):
    """Dimension along which a 2-D coordinate changes the most."""
    values = coord.values.astype(np.float64)
    changes = [np.nanmean(np.abs(np.diff(values, axis=axis))) for axis in (0, 1)]
    return coord.dims[int(np.argmax(changes))]


def _horizontal_pair(data, spatial):
    """Return ``(x_dim, y_dim)`` among the spatial dims of ``data``.

    Surface dimensions are taken from :func:`get_surface_dims` when exactly
    two of them are spatial; otherwise the last two spatial dimensions are
    used, the CF ``(..., lat, lon)`` order. Within the pair, a 2-D
    longitude decides: x is the dimension it changes most along. Failing
    that, names that look like x/lon and y/lat decide, and failing that the
    last one is x.
    """
    surface = [dim for dim in get_surface_dims(data.to_dataset()) if dim in spatial]
    if len(surface) != 2:
        logger.info(f"{data.name}: no surface dimensions found, using the last two")
        surface = spatial[-2:]
    first, second = surface
    longitudes = [
        coord
        for name, coord in _coords_2d(data, surface).items()
        if _is_x_coord(name, coord)
    ]
    if longitudes:
        x_dim = _varies_most_along(longitudes[0])
        return x_dim, (second if x_dim == first else first)
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


def frame_array(data, layout, index=None, background=0.0, placement=None):
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
    placement : Placement, optional
        Resampling applied to the frame (see :func:`volume_placement`).
    """
    x_dim, y_dim, vertical, animate = layout
    if animate:
        data = data.isel({animate: index or 0})
    if vertical:
        values = data.transpose(x_dim, y_dim, vertical).values
    else:
        values = data.transpose(x_dim, y_dim).values[..., np.newaxis]
    values = np.nan_to_num(values.astype(np.float32), nan=background)
    if placement is not None:
        values = placement.apply(values, background)
    return np.ascontiguousarray(values)


def finite_range(data):
    """Return ``(min, max)`` of the finite values of ``data``, ``(0, 0)`` if none.

    A lazily loaded (dask) array is reduced in one pass that computes both
    ends, rather than one pass each.
    """
    low, high = data.min(skipna=True), data.max(skipna=True)
    if data.chunks is not None:
        import dask

        low, high = dask.compute(low, high)
    low, high = float(low), float(high)
    if not (np.isfinite(low) and np.isfinite(high)):
        return 0.0, 0.0
    return low, high


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


@dataclass
class Placement:
    """Where the voxels go, and how a frame is resampled to land there.

    ``origin`` and ``step`` give the position of the first voxel and the
    voxel size along x, y and the vertical axis, before the node's vertical
    scale. :meth:`apply` turns a frame in ``(x, y, vertical)`` order into
    voxels: ``take`` holds, per axis, the source position of each voxel (a
    descending coordinate is reversed, an uneven one resampled), or ``None``
    to keep the axis as it is. For curvilinear coordinates ``flat`` gives
    the source column of every voxel column and ``outside`` marks columns
    with no data near them. ``notes`` tell the user what was resampled.
    """

    origin: list
    step: list
    take: list
    flat: np.ndarray = None
    outside: np.ndarray = None
    notes: list = field(default_factory=list)

    def apply(self, array, background=0.0):
        """Resample a ``(x, y, vertical)`` frame onto the voxel grid."""
        if self.flat is not None:
            nx, ny, nz = array.shape
            columns = array.reshape(nx * ny, nz)[self.flat]
            columns[self.outside] = background
            array = columns.reshape(nx, ny, nz)
        for axis, take in enumerate(self.take):
            if take is not None:
                array = np.take(array, take, axis=axis)
        return array

    def transform(self, vertical_scale=1.0):
        """Object ``(location, scale)`` placing the voxels."""
        location = (self.origin[0], self.origin[1], self.origin[2] * vertical_scale)
        scale = (self.step[0], self.step[1], self.step[2] * vertical_scale)
        return location, scale


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


def nearest_positions(values, targets):
    """Position in ``values`` of the value nearest to each of ``targets``.

    ``values`` may be in any order; ties go to the smaller value.
    """
    order = np.argsort(values, kind="stable")
    ordered = values[order]
    right = np.clip(np.searchsorted(ordered, targets), 1, ordered.size - 1)
    left = right - 1
    use_left = (targets - ordered[left]) <= (ordered[right] - targets)
    return order[np.where(use_left, left, right)]


def _usable(values):
    """True for at least two finite numbers, which can place voxels."""
    return (
        values.size >= 2
        and np.issubdtype(values.dtype, np.number)
        and bool(np.isfinite(values).all())
    )


def _reversed(count):
    """Positions ``count - 1`` down to 0."""
    return np.arange(count)[::-1].copy()


def _even_placement(values):
    """``(origin, step, take)`` of evenly spaced ``values``, else ``None``.

    Descending values are reversed so the step stays positive.
    """
    spacing = axis_spacing(values)
    if spacing is None:
        return None
    origin, step = spacing
    if step > 0:
        return origin, step, None
    return float(values[-1]), -step, _reversed(values.size)


def axis_placement(name, values):
    """Place one horizontal axis on its 1-D coordinate ``values``.

    Evenly spaced values set the origin and the voxel size; descending ones
    are reversed so the size stays positive. Uneven values are resampled
    onto as many evenly spaced ones over the same extent, by nearest
    neighbour. Values that cannot place voxels (dates, NaN, a single value)
    leave the axis in index space.

    Returns
    -------
    tuple
        ``(origin, step, take, note)``, ``note`` being ``""`` unless the
        axis was resampled.
    """
    values = np.asarray(values)
    if not _usable(values):
        return 0.0, 1.0, None, ""
    values = values.astype(np.float64)
    even = _even_placement(values)
    if even is not None:
        return (*even, "")
    low, high = float(values.min()), float(values.max())
    if low == high:
        return low, 1.0, None, ""
    count = values.size
    take = nearest_positions(values, np.linspace(low, high, count))
    note = f"{name} is unevenly spaced:\nresampled onto {count} even steps."
    return low, (high - low) / (count - 1), take, note


def vertical_placement(data, vertical):
    """Place the vertical axis on its coordinate, if evenly spaced.

    A CF ``positive = "down"`` coordinate (depth, pressure) is negated
    first, so deeper levels sit lower. An evenly spaced numeric coordinate
    sets the origin and the voxel height; anything else (dates for a
    space-time cube, uneven levels) gives one voxel per level, ordered
    bottom-up, and uneven levels get a note.

    Returns
    -------
    tuple
        ``(origin, step, take, note)``, all before the vertical scale.
    """
    values = _vertical_values(data, vertical)
    if values is None:
        return 0.0, 1.0, None, ""
    even = _even_placement(values)
    if even is not None:
        return (*even, "")
    take = _reversed(values.size) if values[-1] < values[0] else None
    note = f"{vertical} is unevenly spaced:\none voxel per level."
    return 0.0, 1.0, take, note


def _vertical_values(data, vertical):
    """The vertical coordinate as floats, up positive, or ``None``.

    ``None`` when there is no vertical axis or its values cannot place
    voxels (dates, NaN, a single level).
    """
    if not vertical:
        return None
    coord = data[vertical]
    values = np.asarray(coord.values)
    if not _usable(values):
        return None
    values = values.astype(np.float64)
    if str(coord.attrs.get("positive", "")).lower() == "down":
        return -values
    return values


def curvilinear_pair(data, x_dim, y_dim):
    """2-D longitude and latitude of ``data`` over the horizontal dims.

    Returns
    -------
    tuple or None
        ``(x_name, x_values, y_name, y_values)``, the arrays in
        ``(x_dim, y_dim)`` order, or ``None`` when ``data`` has no such
        pair of coordinates.
    """
    coords = _coords_2d(data, (x_dim, y_dim))
    xs = [name for name, coord in coords.items() if _is_x_coord(name, coord)]
    ys = [name for name, coord in coords.items() if _is_y_coord(name, coord)]
    ys = [name for name in ys if name not in xs[:1]]
    if not xs or not ys:
        return None
    x_name, y_name = xs[0], ys[0]

    def values(name):
        return data[name].transpose(x_dim, y_dim).values.astype(np.float64)

    return x_name, values(x_name), y_name, values(y_name)


def curvilinear_placement(x_name, x_values, y_name, y_values):
    """Resample a curvilinear grid onto a regular one, by nearest neighbour.

    The regular grid spans the extent of the coordinates with as many
    points along each axis as the source. Each voxel column takes the
    source column nearest to it; columns further than
    :data:`CURVILINEAR_REACH` times the local source spacing from any
    source point, outside the data's footprint, stay empty.

    Parameters
    ----------
    x_name, y_name : str
        Coordinate names, for the note.
    x_values, y_values : numpy.ndarray
        2-D coordinates in ``(x, y)`` voxel order.

    Returns
    -------
    tuple or None
        ``(origin, step, flat, outside, note)``, or ``None`` when fewer
        than two points have finite coordinates.
    """
    from scipy.spatial import cKDTree

    nx, ny = x_values.shape
    valid = np.isfinite(x_values) & np.isfinite(y_values)
    if valid.sum() < 2:
        return None
    sources = np.column_stack([x_values[valid], y_values[valid]])
    source_columns = np.flatnonzero(valid.ravel())
    low, high = sources.min(axis=0), sources.max(axis=0)
    axes = [np.linspace(low[i], high[i], n) for i, n in ((0, nx), (1, ny))]
    targets = np.column_stack([np.repeat(axes[0], ny), np.tile(axes[1], nx)])

    tree = cKDTree(sources)
    distance, nearest = tree.query(targets)
    neighbours, _ = tree.query(sources, k=min(5, len(sources)))
    reach = CURVILINEAR_REACH * neighbours[:, -1]
    outside = distance > reach[nearest]

    step = [
        (high[i] - low[i]) / (n - 1) if n > 1 and high[i] > low[i] else 1.0
        for i, n in ((0, nx), (1, ny))
    ]
    note = (
        f"{x_name}/{y_name} are curvilinear:"
        f"\nresampled onto a regular {nx} x {ny} grid."
    )
    return [float(low[0]), float(low[1])], step, source_columns[nearest], outside, note


def _rectilinear(x_values, y_values):
    """1-D x and y when 2-D coordinates only vary along their own axis."""
    same_x = np.allclose(x_values, x_values[:, :1], equal_nan=True)
    same_y = np.allclose(y_values, y_values[:1, :], equal_nan=True)
    if same_x and same_y:
        return x_values[:, 0], y_values[0, :]
    return None


def volume_placement(data, layout):
    """Work out where the voxels of ``data`` go (see :class:`Placement`).

    Horizontal axes use the 2-D longitude/latitude of ``data`` when it has
    them (reduced to 1-D when they only vary along their own axis),
    otherwise the dimension coordinates. The vertical axis follows
    :func:`vertical_placement`.

    Parameters
    ----------
    data : xarray.DataArray
        Variable with its slicing applied.
    layout : tuple
        As returned by :func:`volume_layout`.
    """
    x_dim, y_dim, vertical, _ = layout
    z_origin, z_step, z_take, z_note = vertical_placement(data, vertical)
    axes, pair = _horizontal_axes(data, x_dim, y_dim)
    curvilinear = curvilinear_placement(*pair) if pair is not None else None
    if curvilinear is not None:
        origin, step, flat, outside, note = curvilinear
        take, notes = [None, None], [note]
    else:
        origin, step, take, notes = _rectilinear_placement(axes)
        flat = outside = None
    return Placement(
        origin + [z_origin],
        step + [z_step],
        take + [z_take],
        flat,
        outside,
        [text for text in notes + [z_note] if text],
    )


def _horizontal_axes(data, x_dim, y_dim):
    """The 1-D x and y coordinates, and any curvilinear pair.

    Returns
    -------
    tuple
        ``(axes, pair)``. ``axes`` holds ``(name, values)`` for x and y:
        the 2-D longitude/latitude reduced to 1-D when they only vary along
        their own axis, otherwise the dimension coordinates. ``pair`` is
        the result of :func:`curvilinear_pair` when those 2-D coordinates
        are truly curvilinear, ``None`` otherwise.
    """
    pair = curvilinear_pair(data, x_dim, y_dim)
    if pair is not None:
        x_name, x_values, y_name, y_values = pair
        reduced = _rectilinear(x_values, y_values)
        if reduced is not None:
            return ((x_name, reduced[0]), (y_name, reduced[1])), None
    return ((x_dim, data[x_dim].values), (y_dim, data[y_dim].values)), pair


def _rectilinear_placement(axes):
    """Lists of origin, step, take and note of 1-D axes, one item per axis."""
    columns = zip(*(axis_placement(name, values) for name, values in axes))
    return [list(column) for column in columns]


# Placement of the last bake per node, reused by the current-frame mode so
# a curvilinear grid is not matched again on every frame. Keyed by the
# node's pointer; the bake token tells a stale entry.
_PLACEMENTS = {}


def _cached_placement(node, data, layout):
    """Placement of the node's last bake, computed again when it is stale."""
    cached = _PLACEMENTS.get(node.as_pointer())
    if cached is not None and cached[0] == node.bake_token:
        return cached[1]
    placement = volume_placement(data, layout)
    _PLACEMENTS[node.as_pointer()] = (node.bake_token, placement)
    return placement


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

    Returns
    -------
    tuple
        ``(obj, notes)``: the Volume object and the messages for the user,
        as ``{"INFO": [...], "WARNING": [...]}``. Info notes say what was
        resampled; the warning says the files are temporary.

    Raises
    ------
    ValueError
        With the message shown on the node.
    """
    variable, data, layout = volume_data(node)
    placement = volume_placement(data, layout)
    frames = frame_count(data, layout)
    obj = look_up_volume_object(node.volume_obj_name)
    value_range = bake_range(obj, data)

    node.bake_token += 1  # new file names, so Blender's grid cache misses
    _PLACEMENTS[node.as_pointer()] = (node.bake_token, placement)
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
    obj.location, obj.scale = placement.transform(node.vertical_scale)
    node.baked_z_origin, node.baked_z_step = placement.origin[2], placement.step[2]
    write_object_range(obj, value_range)
    logger.info(
        f"{node.name}: wrote {len(indices)} VDB file(s) of {variable} "
        f"({', '.join(filter(None, layout))}) to {directory}"
    )
    temporary = _vdb_base(node)[1]
    return obj, {
        "INFO": list(placement.notes),
        "WARNING": [UNSAVED_WARNING] if temporary else [],
    }


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
