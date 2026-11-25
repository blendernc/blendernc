"""Fields written onto a mesh: point values, their range, and why a
variable cannot be written as a texture or an animation.

Nothing here imports Blender (see :mod:`blendernc.core`).
"""

import logging
from itertools import combinations
from math import prod

import numpy as np

logger = logging.getLogger(__name__)


# Advice given when a variable has too many dimensions to be written onto a
# mesh as a static texture, keyed by its number of dimensions. Anything
# above four falls back to the four-dimensional hint.
TEXTURE_DIM_HINTS = {
    3: (
        "Use a Datacube Animate Texture node to animate the extra dimension,"
        " or a Datacube Volume node."
    ),
    4: "Use a Datacube Select node to pick a slice first.",
}


# Mesh custom property recording the (rows, columns) dimensions of a grid.
GRID_DIMS_PROPERTY = "BlenderNC grid dims"


def mesh_grid_dims(mesh):
    """Return the ``(rows, columns)`` dims ``mesh`` was baked on, or ``None``."""
    value = mesh.get(GRID_DIMS_PROPERTY) if mesh is not None else None
    return tuple(value.split(",")) if value else None


def field_to_point_values(data, dims=None):
    """Flatten a 2-D field into the vertex order of a baked grid.

    Parameters
    ----------
    data : xarray.DataArray
        Two-dimensional array whose dimensions span the mesh.
    dims : tuple of str, optional
        ``(rows, columns)`` dimensions the grid was baked with (see
        :func:`mesh_grid_dims`). When ``data`` has the same dimensions in
        another order it is transposed first, so ``(x, y)`` and ``(y, x)``
        fields land on the same vertices.

    Returns
    -------
    numpy.ndarray
        1-D ``float32`` array with one value per vertex. Missing values stay
        NaN; :func:`write_point_attribute` zeroes them when writing.
    """
    if dims and set(dims) == set(data.dims):
        data = data.transpose(*dims)
    return np.ascontiguousarray(data.values.transpose(1, 0).ravel(), dtype=np.float32)


# Custom properties on the mesh that hold the range of the written field.
RANGE_PROPERTIES = ("Min value", "Max value")


def field_range(values):
    """Return ``(min, max)`` of the finite values, or ``(0.0, 0.0)`` if none.

    One pass over an array that is already in memory; sampling would be
    slower to set up than the reduction itself.
    """
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return 0.0, 0.0
    return float(finite.min()), float(finite.max())


# Advice for a variable an animate texture node cannot animate, keyed by its
# number of dimensions, four and more sharing one entry.
ANIMATED_DIM_HINTS = {
    2: "Use a Datacube Texture node for a 2D field.",
    4: "Use a Datacube Select node to pick a slice first.",
}


def animated_field_error(data, mesh):
    """Find the dimension of ``data`` to animate over ``mesh``, or say why not.

    Returns
    -------
    tuple
        ``(dim, "")``, or ``(None, message)`` with two lines: what is wrong,
        then what to do about it.
    """
    ndim = len(data.dims)
    dims = ", ".join(str(dim) for dim in data.dims)
    if ndim != 3:
        hint = ANIMATED_DIM_HINTS.get(min(ndim, 4), "An animation needs a 3D field.")
        return None, f"{data.name} is {ndim}D ({dims}).\n{hint}"
    dim = animation_dim(data, mesh)
    if dim is None:
        return None, (
            f"No two dimensions of {data.name} ({dims}) match the mesh's "
            f"{len(mesh.vertices)} vertices.\n"
            "Bake the grid from the coordinates of this variable."
        )
    return dim, ""


def animation_dim(data, mesh):
    """The dimension of a 3-D ``data`` to spread over frames on ``mesh``.

    The other two must span the mesh: the dimensions the grid was baked on
    when it recorded them, otherwise the first pair whose sizes multiply to
    the vertex count. ``None`` when no pair does.
    """
    pairs = [
        set(pair)
        for pair in combinations(data.dims, 2)
        if prod(data.sizes[dim] for dim in pair) == len(mesh.vertices)
    ]
    baked = set(mesh_grid_dims(mesh) or ())
    grid = baked if baked in pairs else next(iter(pairs), None)
    if grid is None:
        return None
    return next(dim for dim in data.dims if dim not in grid)


def animation_frame(data, dim, frame):
    """The 2-D field of ``data`` shown at scene frame ``frame``.

    Frame 0 shows the first step along ``dim``; frames past the last step
    hold it, and negative frames hold the first.
    """
    return data.isel({dim: min(max(frame, 0), data.sizes[dim] - 1)})


def texture_field_error(data, mesh):
    """Explain why ``data`` cannot be written onto ``mesh`` as a 2-D texture.

    Only dimensions are counted, so an index picked with a Datacube Select
    node, which xarray keeps as a scalar coordinate, does not add to the
    total.

    Parameters
    ----------
    data : xarray.DataArray
        Variable with its slicing already applied.
    mesh : bpy.types.Mesh
        Mesh the field would be written onto.

    Returns
    -------
    str
        Empty when the field is 2-D and has one value per vertex. Otherwise
        two lines: what is wrong, then what to do about it.
    """
    ndim = len(data.dims)
    dims = ", ".join(str(dim) for dim in data.dims)
    problem = f"{data.name} is {ndim}D ({dims})."
    if ndim == 2:
        size, vertices = prod(data.shape), len(mesh.vertices)
        if size != vertices:
            return (
                f"{data.name} has {size} values ({dims}), mesh has {vertices} vertices."
                "\nBake the grid from the coordinates of this variable."
            )
        baked = mesh_grid_dims(mesh)
        if baked and set(baked) != set(data.dims):
            return (
                f"{data.name} spans ({dims}), the grid spans ({', '.join(baked)})."
                "\nBake the grid from the coordinates of this variable."
            )
        return ""
    if ndim < 2:
        return problem + "\nA texture needs a 2D field."
    hint = TEXTURE_DIM_HINTS.get(ndim, TEXTURE_DIM_HINTS[4])
    return problem + "\n" + hint
