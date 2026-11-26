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
# mesh as a static texture, keyed by how many more dimensions it has than
# the grid. Anything above two falls back to the two-dimension hint.
TEXTURE_DIM_HINTS = {
    1: (
        "Use a Datacube Animate Texture node to animate the extra dimension,"
        " or a Datacube Volume node."
    ),
    2: "Use a Datacube Select node to pick a slice first.",
}


# Mesh custom property recording the (rows, columns) dimensions of a grid.
GRID_DIMS_PROPERTY = "BlenderNC grid dims"


def mesh_grid_dims(mesh):
    """Return the dims ``mesh`` was baked on, or ``None``.

    ``(rows, columns)`` for a grid, ``(dim,)`` for scattered points.
    """
    value = mesh.get(GRID_DIMS_PROPERTY) if mesh is not None else None
    return tuple(value.split(",")) if value else None


def mesh_field_ndim(mesh):
    """Number of dimensions a texture over ``mesh`` has.

    That of the dims the mesh was baked on: one for scattered points, two
    for a grid. A mesh BlenderNC did not bake takes 2-D fields.
    """
    baked = mesh_grid_dims(mesh)
    return len(baked) if baked else 2


def field_to_point_values(data, dims=None):
    """Flatten a field into the vertex order of a baked grid.

    Parameters
    ----------
    data : xarray.DataArray
        Array whose dimensions span the mesh: two for a grid, one for
        scattered points.
    dims : tuple of str, optional
        Dimensions the grid was baked with (see :func:`mesh_grid_dims`).
        When ``data`` has the same dimensions in another order it is
        transposed first, so ``(x, y)`` and ``(y, x)`` fields land on the
        same vertices.

    Returns
    -------
    numpy.ndarray
        1-D ``float32`` array with one value per vertex. Missing values stay
        NaN; :func:`write_point_attribute` zeroes them when writing.
    """
    if dims and set(dims) == set(data.dims):
        data = data.transpose(*dims)
    values = data.values
    if values.ndim == 2:
        values = values.transpose(1, 0)  # Mesh Grid runs column by column
    return np.ascontiguousarray(values.ravel(), dtype=np.float32)


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


# Advice for a variable an animate texture node cannot animate, keyed by how
# many more dimensions it has than the grid, two and more sharing one entry.
ANIMATED_DIM_HINTS = {
    0: "Use a Datacube Texture node for a {grid}D field.",
    2: "Use a Datacube Select node to pick a slice first.",
}


def animated_field_error(data, mesh):
    """Find the dimension of ``data`` to animate over ``mesh``, or say why not.

    The field needs one dimension more than the grid: 3-D over a grid,
    2-D over scattered points.

    Returns
    -------
    tuple
        ``(dim, "")``, or ``(None, message)`` with two lines: what is wrong,
        then what to do about it.
    """
    ndim, grid = len(data.dims), mesh_field_ndim(mesh)
    dims = ", ".join(str(dim) for dim in data.dims)
    if ndim != grid + 1:
        hint = ANIMATED_DIM_HINTS.get(
            min(max(ndim - grid, -1), 2), "An animation needs a {frames}D field."
        )
        hint = hint.format(grid=grid, frames=grid + 1)
        return None, f"{data.name} is {ndim}D ({dims}).\n{hint}"
    dim = animation_dim(data, mesh)
    if dim is None:
        return None, (
            f"No {_dims_word(grid)} of {data.name} ({dims}) match the mesh's "
            f"{len(mesh.vertices)} vertices.\n"
            "Bake the grid from the coordinates of this variable."
        )
    return dim, ""


def _dims_word(count):
    """``"dimension"`` for one, ``"two dimensions"`` for two."""
    return "dimension" if count == 1 else "two dimensions"


def animation_dim(data, mesh):
    """The dimension of ``data`` to spread over frames on ``mesh``.

    The others must span the mesh: the dimensions the grid was baked on
    when it recorded them, otherwise the first combination whose sizes
    multiply to the vertex count. ``None`` when none does.
    """
    spans = [
        set(span)
        for span in combinations(data.dims, mesh_field_ndim(mesh))
        if prod(data.sizes[dim] for dim in span) == len(mesh.vertices)
    ]
    baked = set(mesh_grid_dims(mesh) or ())
    grid = baked if baked in spans else next(iter(spans), None)
    if grid is None:
        return None
    return next(dim for dim in data.dims if dim not in grid)


def animation_frame(data, dim, frame):
    """The field of ``data`` shown at scene frame ``frame``.

    Frame 0 shows the first step along ``dim``; frames past the last step
    hold it, and negative frames hold the first.
    """
    return data.isel({dim: min(max(frame, 0), data.sizes[dim] - 1)})


def texture_field_error(data, mesh):
    """Explain why ``data`` cannot be written onto ``mesh`` as a texture.

    The field needs the dimensions of the grid: two for a grid, one for
    scattered points (see :func:`mesh_field_ndim`). Only dimensions are
    counted, so an index picked with a Datacube Select node, which xarray
    keeps as a scalar coordinate, does not add to the total.

    Parameters
    ----------
    data : xarray.DataArray
        Variable with its slicing already applied.
    mesh : bpy.types.Mesh
        Mesh the field would be written onto.

    Returns
    -------
    str
        Empty when the field has the grid's dimensions and one value per
        vertex. Otherwise two lines: what is wrong, then what to do about it.
    """
    ndim, grid = len(data.dims), mesh_field_ndim(mesh)
    dims = ", ".join(str(dim) for dim in data.dims)
    problem = f"{data.name} is {ndim}D ({dims})."
    if ndim == grid:
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
    if ndim < grid:
        return problem + f"\nA texture on this mesh needs a {grid}D field."
    return problem + "\n" + TEXTURE_DIM_HINTS[min(ndim - grid, 2)]
