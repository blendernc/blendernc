"""Layout and placement of a Datacube Volume, before any file is written.

A 3-D or 4-D variable becomes voxels: the horizontal dimensions become the
voxel x and y axes, the remaining spatial dimension the vertical axis, and an
optional "animate" dimension is spread over frames. Voxels sit on the
coordinates (see :class:`Placement`): evenly spaced ones set the voxel size
directly, descending ones are flipped, and unevenly spaced or curvilinear
horizontal ones are resampled onto a regular grid by nearest neighbour.
Unevenly spaced vertical levels are interpolated onto even steps at their
true height (see :func:`vertical_placement`), or kept one voxel per level.

Nothing here imports Blender (see :mod:`blendernc.core`).
"""

import hashlib
import logging
import re
from dataclasses import dataclass, field

import numpy as np

from .grid import get_surface_dims

logger = logging.getLogger(__name__)


# Values of the node's ``animate_dim`` enum that are not dimension names.
ANIMATE_AUTO = "AUTO"


ANIMATE_NONE = "NONE"


# Values of the node's ``vertical_mode`` enum: unevenly spaced levels are
# interpolated onto even steps at their height, or stacked one voxel each.
VERTICAL_DEPTH = "DEPTH"


VERTICAL_LEVELS = "LEVELS"


# Unevenly spaced levels are resampled onto at most this many times as many
# even steps, unless the node asks for a number of voxels.
MAX_LEVEL_FACTOR = 2


# Relative spacing error tolerated before a coordinate counts as uneven.
SPACING_RTOL = 1e-3


# A voxel column of a resampled curvilinear grid stays empty when its
# nearest source point is further away than this fraction of the source's
# local spacing (the distance to the furthest of its four nearest points).
CURVILINEAR_REACH = 0.75


_X_NAME = re.compile(r"(^|[^a-z])(x|lon)")


_Y_NAME = re.compile(r"(^|[^a-z])(y|lat)")


# CF attributes that mark a horizontal coordinate, besides its name.
_X_STANDARD_NAMES = {"longitude", "grid_longitude", "projection_x_coordinate"}


_Y_STANDARD_NAMES = {"latitude", "grid_latitude", "projection_y_coordinate"}


_X_UNITS = {"degrees_east", "degree_east", "degrees_e", "degree_e"}


_Y_UNITS = {"degrees_north", "degree_north", "degrees_n", "degree_n"}


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


def mask_grid_name(variable):
    """Name of the grid marking where ``variable`` has data (1) or not (0)."""
    return f"{variable}_mask"


def frame_values(data, layout, index=None, placement=None):
    """Return one frame of ``data`` as a ``(x, y, vertical)`` float32 array.

    Missing values, infinite ones included, are NaN.

    Parameters
    ----------
    data : xarray.DataArray
        Variable with its slicing applied; missing values may be NaN.
    layout : tuple
        As returned by :func:`volume_layout`.
    index : int, optional
        Position along the animate dimension; ignored when static.
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
    values = values.astype(np.float32)  # a copy, changed in place below
    values[np.isinf(values)] = np.nan
    if placement is not None:
        values = placement.apply(values)
    return values


def frame_grids(data, layout, index=None, placement=None, background=0.0):
    """Return the value and mask arrays of one frame, for its two VDB grids.

    The mask is 1 where the frame has data and 0 where it is missing. The
    values are the frame's, with ``background`` where data is missing.
    Missing data is filled after the placement, so interpolated levels never
    blend real values with the background.

    Parameters
    ----------
    data, layout, index, placement
        As for :func:`frame_values`.
    background : float, optional
        Value of missing voxels, which become inactive.

    Returns
    -------
    tuple
        ``(values, mask)``, contiguous ``(x, y, vertical)`` float32 arrays.
    """
    values = frame_values(data, layout, index, placement)
    # C order, whatever the strides the placement left: copyFromArray reads
    # the buffer in C order.
    mask = np.isfinite(values).astype(np.float32, order="C")
    values = np.nan_to_num(values, nan=background)
    return np.ascontiguousarray(values), mask


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
    with no data near them. Uneven levels placed at their height have
    ``vertical``, the levels and weights of :func:`depth_interpolation`.
    ``notes`` tell the user what was resampled.
    """

    origin: list
    step: list
    take: list
    flat: np.ndarray = None
    outside: np.ndarray = None
    vertical: tuple = None
    notes: list = field(default_factory=list)

    def apply(self, array):
        """Resample a ``(x, y, vertical)`` float frame onto the voxel grid.

        Missing values may be NaN (see :func:`interpolate_levels`); columns
        outside a curvilinear grid's data become NaN too.
        """
        if self.flat is not None:
            nx, ny, nz = array.shape
            columns = array.reshape(nx * ny, nz)[self.flat]
            columns[self.outside] = np.nan
            array = columns.reshape(nx, ny, nz)
        for axis, take in enumerate(self.take):
            if take is not None:
                array = np.take(array, take, axis=axis)
        if self.vertical is not None:
            array = interpolate_levels(array, *self.vertical)
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


def vertical_voxel_count(values, requested=0):
    """Number of even steps that uneven, distinct levels are resampled onto.

    A positive ``requested`` count wins (at least 2). Otherwise the finest
    spacing between levels sets the step over their extent, capped at
    :data:`MAX_LEVEL_FACTOR` times the number of levels, so a frame holds
    at most that many times the voxels of the data.
    """
    if requested > 0:
        return max(int(requested), 2)
    levels = np.sort(values)
    ratio = (levels[-1] - levels[0]) / np.diff(levels).min()
    wanted = int(np.ceil(ratio - SPACING_RTOL)) + 1  # 11.000000000000004 is 11
    return min(wanted, MAX_LEVEL_FACTOR * values.size)


def depth_interpolation(values, count):
    """Levels and weights resampling distinct ``values`` onto ``count`` steps.

    The steps are evenly spaced from the lowest to the highest value, which
    may come in any order.

    Returns
    -------
    tuple
        ``(lower, upper, weight)``: per step, the positions in ``values`` of
        the levels below and above it, and how far it lies from the first
        towards the second, from 0 to 1 (float32).
    """
    order = np.argsort(values, kind="stable")
    ordered = values[order]
    targets = np.linspace(ordered[0], ordered[-1], count)
    position = np.interp(targets, ordered, np.arange(ordered.size))
    below = np.minimum(np.floor(position).astype(int), ordered.size - 2)
    weight = (position - below).astype(np.float32)
    return order[below], order[below + 1], weight


def interpolate_levels(array, lower, upper, weight):
    """Blend the levels of a ``(x, y, vertical)`` array onto new levels.

    New level ``k`` is ``array[..., lower[k]]`` moved by ``weight[k]``
    towards ``array[..., upper[k]]``. Where either one is missing (NaN),
    the nearer one is used instead, so data next to a missing level, such
    as the sea floor, reaches half way to it.
    """
    below, above = array[..., lower], array[..., upper]
    blended = below + (above - below) * weight
    missing = np.isnan(blended)
    if missing.any():
        nearest = np.where(weight <= 0.5, below, above)
        blended[missing] = nearest[missing]
    return blended


def vertical_placement(data, vertical, mode=VERTICAL_DEPTH, voxels=0):
    """Place the vertical axis on its coordinate.

    A CF ``positive = "down"`` coordinate (depth, pressure) is negated
    first, so deeper levels sit lower. An evenly spaced numeric coordinate
    sets the origin and the voxel height. Unevenly spaced levels are
    interpolated onto even steps at their height in :data:`VERTICAL_DEPTH`
    mode (see :func:`vertical_voxel_count`); in :data:`VERTICAL_LEVELS`
    mode, or when a level repeats, they give one voxel per level, ordered
    bottom-up. Uneven levels get a note either way. Anything else (dates
    for a space-time cube) gives one voxel per level.

    Parameters
    ----------
    data : xarray.DataArray
        Variable with its slicing applied.
    vertical : str
        Vertical dimension, or ``""``.
    mode : str, optional
        Value of the node's ``vertical_mode`` enum.
    voxels : int, optional
        Number of steps for uneven levels in depth mode; 0 picks one.

    Returns
    -------
    tuple
        ``(origin, step, take, interp, note)``, origin and step before the
        vertical scale; ``interp`` is ``None`` unless the levels are
        interpolated (see :func:`depth_interpolation`).
    """
    values = _vertical_values(data, vertical)
    if values is None:
        return 0.0, 1.0, None, None, ""
    even = _even_placement(values)
    if even is not None:
        return (*even, None, "")
    if mode == VERTICAL_DEPTH and np.unique(values).size == values.size:
        return _depth_placement(vertical, values, voxels)
    take = _reversed(values.size) if values[-1] < values[0] else None
    note = f"{vertical} is unevenly spaced:\none voxel per level."
    return 0.0, 1.0, take, None, note


def _depth_placement(name, values, voxels):
    """:func:`vertical_placement` of uneven, distinct levels, at their height."""
    count = vertical_voxel_count(values, voxels)
    low, high = float(values.min()), float(values.max())
    step = (high - low) / (count - 1)
    note = (
        f"{name} is unevenly spaced:"
        f"\nresampled onto {count} even steps of {step:.3g}."
    )
    return low, step, None, depth_interpolation(values, count), note


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


def volume_placement(data, layout, vertical_mode=VERTICAL_DEPTH, vertical_voxels=0):
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
    vertical_mode, vertical_voxels : optional
        The node's settings for uneven levels (see
        :func:`vertical_placement`).
    """
    x_dim, y_dim, vertical, _ = layout
    z_origin, z_step, z_take, z_interp, z_note = vertical_placement(
        data, vertical, vertical_mode, vertical_voxels
    )
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
        flat=flat,
        outside=outside,
        vertical=z_interp,
        notes=[text for text in notes + [z_note] if text],
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


def placement_key(data, layout, vertical_mode=VERTICAL_DEPTH, vertical_voxels=0):
    """Digest of everything that decides where the voxels of ``data`` go.

    That is the layout, the node's settings for uneven levels, the length
    of the x, y and vertical dimensions, and the values and ``positive``
    attribute of every coordinate lying on those dimensions. Two bakes with
    the same key place their voxels alike, whatever the variable or the
    index picked along a dimension the volume does not show. The animated
    dimension only sets the number of frames, so its length is left out.
    """
    spatial = {dim for dim in layout[:3] if dim}
    digest = hashlib.blake2b(digest_size=16)
    digest.update(repr(layout).encode())
    digest.update(f"{vertical_mode}|{int(vertical_voxels)}".encode())
    digest.update(repr(sorted((dim, data.sizes[dim]) for dim in spatial)).encode())
    for name, coord in sorted(data.coords.items(), key=lambda item: str(item[0])):
        if coord.dims and set(coord.dims) <= spatial:
            positive = coord.attrs.get("positive", "")
            digest.update(f"{name}|{coord.dims}|{positive}".encode())
            digest.update(_value_bytes(coord.values))
    return digest.hexdigest()


def _value_bytes(values):
    """The bytes of a coordinate's values, for :func:`placement_key`."""
    values = np.ascontiguousarray(values)
    if values.dtype.kind == "O":  # strings, cftime dates
        return repr(values.tolist()).encode()
    return values.tobytes()


def clamp_frame(frame, frames):
    """Frame index used at scene frame ``frame`` for ``frames`` frames."""
    return min(max(frame, 0), frames - 1)
