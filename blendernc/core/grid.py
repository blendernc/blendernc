"""Surface dimensions and the 2-D coordinates a Datacube Grid is baked on.

Nothing here imports Blender (see :mod:`blendernc.core`).
"""

import logging
import re
from itertools import combinations
from math import prod

import numpy as np

logger = logging.getLogger(__name__)


# Names that mark a horizontal dimension. ``lon``/``lat`` anywhere in the
# name; ``x``/``y`` only as a token, optionally with one trailing letter so
# that ``xc``, ``xu``, ``xi_rho`` and ``y_rho`` match but ``index`` does not.
SURFACE_DIM_PATTERNS = (
    re.compile(r"lon"),
    re.compile(r"lat"),
    re.compile(r"(^|[^a-z])x[a-z]?([^a-z]|$)"),
    re.compile(r"(^|[^a-z])y[a-z]?([^a-z]|$)"),
)


def is_surface_name(name):
    """Return ``True`` when ``name`` looks like a horizontal dimension."""
    lowered = name.lower()
    return any(pattern.search(lowered) for pattern in SURFACE_DIM_PATTERNS)


def get_surface_dims(dataset):
    """Dimensions that span the horizontal surface of a dataset.

    A dimension qualifies when its name matches ``SURFACE_DIM_PATTERNS`` or
    when any 2-D coordinate is defined over it.

    Parameters
    ----------
    dataset : xarray.Dataset
        Dataset to inspect.

    Returns
    -------
    list of str
        Surface dimension names in dataset order.
    """
    surface = {dim for dim in dataset.dims if is_surface_name(dim)}
    for coord in dataset.coords.values():
        if coord.ndim == 2:
            surface.update(coord.dims)
    order = list(dataset.dims)
    return sorted(surface, key=order.index)


def _unwrap(coords, *names):
    """Replace the ``"data"`` DataArray of each named entry by its values."""
    for name in names:
        coords[name]["data"] = coords[name]["data"].values


def _meshgrid_coords(coords, x_name, y_name):
    """Replace two 1-D coordinates with their 2-D mesh grid, in place.

    Parameters
    ----------
    coords : dict
        Coordinate mapping as returned by :func:`get_grid_coords`.
    x_name, y_name : str
        Keys of the two 1-D coordinates.

    Returns
    -------
    numpy.ndarray
        The 2-D ``X`` array, useful as a shape template.
    """
    x = coords[x_name]["data"].values
    y = coords[y_name]["data"].values

    Y, X = np.meshgrid(y, x, indexing="ij")

    coords[x_name]["data"] = X
    coords[y_name]["data"] = Y

    return X


def _add_missing_coord(coords, name, template):
    """Add a zero-filled coordinate entry shaped like ``template``.

    Parameters
    ----------
    coords : dict
        Coordinate mapping to extend in place.
    name : str
        Key of the new entry (``"X"``, ``"Y"`` or ``"Z"``).
    template : numpy.ndarray
        Array whose shape the new coordinate copies.
    """
    coords[name] = {
        "name": name,
        "size": template.shape,
        "data": np.zeros_like(template),
    }


def _coords_by_ndim(coords):
    """Group coordinate names by the dimensionality of their data.

    Parameters
    ----------
    coords : dict
        Coordinate mapping with a ``"data"`` array per entry.

    Returns
    -------
    dict
        Keys ``1``, ``2`` and ``"gt2"`` mapping to lists of coordinate names.
    """
    groups = {1: [], 2: [], "gt2": []}
    for name, coord in coords.items():
        ndim = coord["data"].ndim
        groups[ndim if ndim in (1, 2) else "gt2"].append(name)
    return groups


def grid_dims(coords):
    """Return the ``(rows, columns)`` dimensions of the grid, or ``None``.

    Two 1-D coordinates give ``(y_dim, x_dim)``, the layout of their mesh
    grid; otherwise the dimensions of the first 2-D coordinate are used.

    Parameters
    ----------
    coords : dict
        Mapping as returned by :func:`get_grid_coords`, still holding
        :class:`xarray.DataArray` objects.
    """
    arrays = [coords[k]["data"] for k in ("X", "Y", "Z") if k in coords]
    if len(arrays) < 2 or not all(hasattr(a, "dims") for a in arrays):
        return None
    first, second = arrays[:2]
    if first.ndim == 1 and second.ndim == 1:
        return (second.dims[0], first.dims[0])
    return next((tuple(a.dims) for a in arrays if a.ndim == 2), None)


def _align_to_grid(coords, dims):
    """Transpose every 2-D array spanning ``dims`` into ``dims`` order."""
    for coord in coords.values():
        data = coord["data"]
        if hasattr(data, "dims") and data.ndim == 2 and set(data.dims) == set(dims):
            coord["data"] = data.transpose(*dims)
            coord["size"] = coord["data"].shape


def get_2D_coords(coords):
    """Expand the grid coordinates to 2-D arrays suitable for a mesh grid.

    Parameters
    ----------
    coords : dict
        Mapping of ``"X"``, ``"Y"`` and/or ``"Z"`` to coordinate entries
        holding a ``"data"`` :class:`xarray.DataArray`.

    Returns
    -------
    dict
        ``coords`` with every entry's ``"data"`` replaced by a 2-D
        :class:`numpy.ndarray`; a missing third axis is filled with zeros.

    Raises
    ------
    ValueError
        If fewer than two axes are present or their dimensions cannot be
        combined.
    """
    dims = grid_dims(coords)
    if dims:
        # A variable stored as (x, y) must land on the same vertices as one
        # stored as (y, x), so every 2-D array follows the grid's order.
        _align_to_grid(coords, dims)

    expected_dims = ["X", "Y", "Z"]

    coord_dims = [dim for dim in expected_dims if dim in coords]
    missing_dims = [dim for dim in expected_dims if dim not in coords]

    if len(coord_dims) < 2:
        raise ValueError("At least two coordinates (X, Y, Z) are required.")

    if len(coord_dims) == 2:
        return _handle_two_coords(coords, coord_dims, missing_dims[0])

    return _handle_three_coords(coords)


def _handle_two_coords(coords, coord_dims, missing_dim):
    """Expand two coordinates and synthesise the missing third one.

    Parameters
    ----------
    coords : dict
        Coordinate mapping to update in place.
    coord_dims : list of str
        The two present axis keys.
    missing_dim : str
        The absent axis key, filled with zeros.

    Returns
    -------
    dict
        The updated mapping.

    Raises
    ------
    ValueError
        If one coordinate is 1-D and the other 2-D.
    """
    x_name, y_name = coord_dims

    x = coords[x_name]["data"]
    y = coords[y_name]["data"]

    if x.ndim == y.ndim == 1:
        template = _meshgrid_coords(coords, x_name, y_name)
    elif x.ndim == y.ndim == 2:
        _unwrap(coords, x_name, y_name)
        template = coords[x_name]["data"]
    else:
        raise ValueError("Coordinates must be either all 1D or all 2D.")

    _add_missing_coord(coords, missing_dim, template)
    return coords


def _handle_2x1d_1x2d(coords, groups):
    """Mesh-grid two 1-D coordinates and unwrap the single 2-D one."""
    _meshgrid_coords(coords, *groups[1])
    _unwrap(coords, *groups[2])
    return coords


def _handle_3x2d(coords, groups):
    """Unwrap three 2-D coordinates to plain arrays."""
    _unwrap(coords, *groups[2])
    return coords


def _handle_animation_coord(coords, groups):
    """Mesh-grid two 1-D coordinates and mark the higher-dimensional one.

    The coordinate with more than two dimensions is flagged with
    ``"animate": True`` and replaced by zeros so it can be animated later.
    """
    logger.warning(
        "A coordinate has more than 2 dimensions. "
        "The additional dimension will be animated over time."
    )

    X = _meshgrid_coords(coords, *groups[1])

    name = groups["gt2"][0]
    coords[name]["animate"] = True
    coords[name]["data"] = np.zeros_like(X)

    return coords


def _handle_three_coords(coords):
    """Dispatch three coordinates to the handler matching their dimensions.

    Parameters
    ----------
    coords : dict
        Coordinate mapping with ``"X"``, ``"Y"`` and ``"Z"`` entries.

    Returns
    -------
    dict
        The updated mapping.

    Raises
    ------
    ValueError
        If the combination of dimensions is not supported.
    """
    groups = _coords_by_ndim(coords)
    pattern = (len(groups[1]), len(groups[2]), len(groups["gt2"]))

    match pattern:
        case (2, 1, 0):
            return _handle_2x1d_1x2d(coords, groups)
        case (0, 3, 0):
            return _handle_3x2d(coords, groups)
        case (2, 0, 1):
            return _handle_animation_coord(coords, groups)
        case (_, _, n) if n > 1:
            raise ValueError("3D coordinates are not yet supported.")
        case _:
            raise ValueError(
                "Expected either two 1D and one 2D coordinate "
                "or three 2D coordinates."
            )


def stack_2D_coords(coords):
    """Flatten X, Y and Z arrays into the layout expected by ``foreach_set``.

    Parameters
    ----------
    coords : dict
        Mapping with 2-D ``"data"`` arrays under ``"X"``, ``"Y"`` and ``"Z"``.

    Returns
    -------
    numpy.ndarray
        1-D array of interleaved ``(x, y, z)`` triplets, one per vertex.
    """
    X = coords.get("X")["data"]
    Y = coords.get("Y")["data"]
    Z = coords.get("Z")["data"]

    flatten_coords = np.stack([X, Y, Z], axis=0).transpose(2, 1, 0).flatten()

    return flatten_coords


def extract_dimensions_of_grid(coords):
    """Return ``(vertices_x, vertices_y)`` for the Mesh Grid node.

    Takes the coordinates after :func:`get_2D_coords`, where X, Y and Z are
    2-D arrays of shape ``(rows, columns)``. :func:`stack_2D_coords` emits
    the vertices column by column, which is the order Mesh Grid uses along
    its X axis, so ``vertices_x`` is the number of columns.

    Parameters
    ----------
    coords : dict
        Mapping with 2-D ``"data"`` arrays under ``"X"``, ``"Y"`` and ``"Z"``.

    Returns
    -------
    tuple of int
        ``(columns, rows)``.

    Raises
    ------
    ValueError
        If the arrays do not share one 2-D shape.
    """
    shapes = {name: coord["data"].shape for name, coord in coords.items()}
    unique = set(shapes.values())
    if len(unique) != 1 or len(next(iter(unique))) != 2:
        listed = ", ".join(f"{name} {shape}" for name, shape in shapes.items())
        raise ValueError(f"X, Y and Z do not form one 2D grid: {listed}.")
    rows, columns = unique.pop()
    return columns, rows


def find_coord_matches(length, dims):
    """Find the dimension combinations whose total size equals ``length``.

    Parameters
    ----------
    length : int
        Target size, typically the vertex count of a mesh.
    dims : dict
        Mapping of dimension name to its shape (tuple) or size (int).

    Returns
    -------
    list of tuple of str
        Matching name combinations, shortest first. Empty when none matches.
    """
    sizes = {
        name: prod(shape) if isinstance(shape, tuple) else shape
        for name, shape in dims.items()
    }

    return [
        combo
        for r in range(1, len(sizes) + 1)
        for combo in combinations(sizes, r)
        if prod(sizes[name] for name in combo) == length
    ]
