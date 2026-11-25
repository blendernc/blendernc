"""Scattered points joined into triangles, for a grid baked on one dimension.

Unstructured models such as FESOM or ICON store each value at a point
located by 1-D coordinates, e.g. ``lon(ncells)`` and ``lat(ncells)``. A
Datacube Grid linked to two such coordinates puts one vertex at each point,
vertex ``i`` being cell ``i``, and joins the vertices with Delaunay
triangles. Triangles much longer than the spacing of the points around
them, which bridge land or the outside of the domain, are dropped.

Longitudes and latitudes are triangulated on the sphere, where points that
are evenly spaced stay evenly spaced near the poles; other coordinates in
their own plane.

Nothing here imports Blender (see :mod:`blendernc.core`).
"""

import logging

import numpy as np

from .grid import is_latitude, is_longitude

logger = logging.getLogger(__name__)


# Triangles whose longest edge is more than this many times the local
# spacing of their points are dropped (see :func:`triangulate_points`).
DEFAULT_MAX_EDGE = 2.5


# Nearest neighbours whose mean distance is the local spacing of a point.
SPACING_NEIGHBOURS = 6


# Once laid out flat, a triangle of a geographic grid spanning more longitude
# than this crosses the antimeridian or goes round a pole.
MAX_LONGITUDE_SPAN = 180.0


def _axis_values(entry, dim):
    """The values of one linked coordinate, which must span ``(dim,)`` only."""
    data = entry["data"]
    if tuple(data.dims) != (dim,):
        spans = ", ".join(map(str, data.dims))
        raise ValueError(
            f"{entry['name']} spans ({spans}), the points span ({dim})."
            "\nLink coordinates over the points only, or select a slice first."
        )
    return np.asarray(data.values, dtype=np.float64)


def point_columns(coords, dim):
    """The X, Y and Z values of scattered points, Z zero when not linked.

    Parameters
    ----------
    coords : dict
        Mapping as returned by :func:`blendernc.utils.get_grid_coords`.
    dim : str
        The dimension X and Y share (see :func:`blendernc.core.grid.grid_dims`).

    Returns
    -------
    list of numpy.ndarray
        Three ``float64`` arrays of one value per point.

    Raises
    ------
    ValueError
        If X or Y is not linked, or a linked coordinate spans other
        dimensions than ``(dim,)``.
    """
    if "X" not in coords or "Y" not in coords:
        raise ValueError(
            f"Points along {dim} need an X and a Y coordinate."
            "\nLink the longitude to X and the latitude to Y."
        )
    columns = [_axis_values(coords[axis], dim) for axis in ("X", "Y")]
    z = coords.get("Z")
    columns.append(_axis_values(z, dim) if z else np.zeros_like(columns[0]))
    return columns


def is_geographic(coords, y_values):
    """True when X is a longitude and Y a latitude within +/-90 degrees."""
    x, y = coords["X"], coords["Y"]
    return (
        is_longitude(x["name"], x["data"])
        and is_latitude(y["name"], y["data"])
        and bool(np.all(np.abs(y_values) <= 90.0))
    )


def _unit_vectors(lon, lat):
    """Points on the unit sphere at longitudes and latitudes in degrees."""
    lon, lat = np.radians(lon), np.radians(lat)
    return np.column_stack(
        [np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)]
    )


def _delaunay(points):
    """Delaunay triangles of 2-D points, or of 3-D points on the unit sphere.

    On the sphere the Delaunay triangulation is the convex hull. Hull facets
    facing the centre are the lid closing a regional cap and are left out.
    """
    from scipy.spatial import ConvexHull, Delaunay, QhullError

    try:
        if points.shape[1] == 2:
            return Delaunay(points).simplices
        hull = ConvexHull(points)
        return hull.simplices[hull.equations[:, -1] < 0]
    except (QhullError, ValueError) as exc:
        raise ValueError(
            f"{len(points)} points cannot be triangulated: too few, or in one line."
            "\nLink coordinates that spread the points over a surface."
        ) from exc


def _local_spacing(points):
    """Mean distance of each point to its nearest neighbours."""
    from scipy.spatial import cKDTree

    k = min(SPACING_NEIGHBOURS + 1, len(points))
    distances, _ = cKDTree(points).query(points, k=k)
    return distances[:, 1:].mean(axis=1)


def _longest_edges(points, triangles):
    """Length of the longest edge of each triangle."""
    corners = points[triangles]
    edges = corners - np.roll(corners, 1, axis=1)
    return np.linalg.norm(edges, axis=2).max(axis=1)


def _short_enough(points, triangles, max_edge):
    """Mask of the triangles no longer than ``max_edge`` times local spacing."""
    spacing = _local_spacing(points)[triangles].max(axis=1)
    return _longest_edges(points, triangles) <= max_edge * spacing


def _counter_clockwise(x, y, triangles):
    """Triangles turning counter-clockwise in ``(x, y)``, flat ones dropped.

    Faces then all point up the Z axis, whatever order the triangulation
    gave their corners in.
    """
    a, b, c = triangles.T
    area = (x[b] - x[a]) * (y[c] - y[a]) - (x[c] - x[a]) * (y[b] - y[a])
    triangles, area = triangles[area != 0], area[area != 0]
    triangles[area < 0] = triangles[area < 0][:, ::-1]
    return np.ascontiguousarray(triangles, dtype=np.int32)


def triangulate_points(x, y, geographic=False, max_edge=DEFAULT_MAX_EDGE):
    """Join scattered points into Delaunay triangles.

    Parameters
    ----------
    x, y : numpy.ndarray
        Coordinates of the points; longitudes and latitudes in degrees when
        ``geographic``.
    geographic : bool, optional
        Triangulate on the sphere and measure lengths there. Triangles that
        cross the antimeridian once laid out flat are dropped.
    max_edge : float, optional
        Drop triangles whose longest edge is more than this many times the
        local spacing of their points (see :data:`SPACING_NEIGHBOURS`); such
        triangles bridge land or the outside of the domain. 0 keeps all.

    Returns
    -------
    numpy.ndarray
        ``(m, 3)`` ``int32`` indices into the points, counter-clockwise in
        ``(x, y)``.

    Raises
    ------
    ValueError
        If the points are too few or in one line.
    """
    if len(x) < 3:
        raise ValueError(
            f"{len(x)} points cannot be triangulated: too few, or in one line."
            "\nLink coordinates that spread the points over a surface."
        )
    points = _unit_vectors(x, y) if geographic else np.column_stack([x, y])
    triangles = _delaunay(points)
    if geographic:
        triangles = triangles[np.ptp(x[triangles], axis=1) <= MAX_LONGITUDE_SPAN]
    if max_edge > 0:
        triangles = triangles[_short_enough(points, triangles, max_edge)]
    return _counter_clockwise(x, y, triangles)


def scattered_mesh(coords, dim, max_edge=DEFAULT_MAX_EDGE):
    """Vertex positions and triangles of the points linked to a grid node.

    Parameters
    ----------
    coords : dict
        Mapping as returned by :func:`blendernc.utils.get_grid_coords`.
    dim : str
        The dimension X and Y share.
    max_edge : float, optional
        See :func:`triangulate_points`.

    Returns
    -------
    tuple of numpy.ndarray
        ``(positions, triangles)``: ``(n, 3)`` ``float32`` positions, vertex
        ``i`` at point ``i``, and ``(m, 3)`` ``int32`` triangles.

    Raises
    ------
    ValueError
        See :func:`point_columns` and :func:`triangulate_points`.
    """
    x, y, z = point_columns(coords, dim)
    geographic = is_geographic(coords, y)
    triangles = triangulate_points(x, y, geographic, max_edge)
    surface = "on the sphere" if geographic else "in the plane"
    logger.info(
        f"Triangulated {len(x)} points along {dim} {surface}: "
        f"{len(triangles)} triangles"
    )
    positions = np.column_stack([x, y, z]).astype(np.float32)
    return positions, triangles
