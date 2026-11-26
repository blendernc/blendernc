"""Unit tests for :mod:`blendernc.core`, which runs without Blender.

Run from the repository root with ``python -m pytest tests/unit``; the
dependencies are numpy, xarray, scipy and pytest. The Blender tests in
``tests/*.test.py`` cover the nodes, operators and panel.
"""

import numpy as np
import pytest
import xarray as xr

from blendernc.core.dataset import (
    coordinate_names,
    dataset_engine,
    find_common_name,
    variable_names,
)
from blendernc.core.fields import (
    GRID_DIMS_PROPERTY,
    animated_field_error,
    animation_dim,
    animation_frame,
    field_range,
    field_to_point_values,
    texture_field_error,
)
from blendernc.core.grid import (
    find_coord_matches,
    get_surface_dims,
    grid_dims,
    is_surface_name,
    unstructured_dims,
)
from blendernc.core.points import scattered_mesh, triangulate_points
from blendernc.core.slicing import (
    build_indexers,
    clamp_index_range,
    encode_slicing_record,
    format_coord_value,
    merge_selector,
    parse_slicing,
    suggested_stride,
    value_index_range,
)
from blendernc.core.volume import (
    axis_placement,
    clamp_frame,
    nearest_positions,
    placement_key,
    volume_layout,
)

NX, NY, NT = 4, 3, 5

# Scattered points of the ``cells`` fixture, before the land box is cut out.
NCELLS = 20000

# (lon_min, lon_max, lat_min, lat_max) of a box holding no point: triangles
# over it bridge "land".
LAND = (-20.0, 40.0, -30.0, 60.0)


class FakeMesh(dict):
    """Just enough of a ``bpy.types.Mesh``: custom properties and vertices."""

    def __init__(self, vertices, grid_dims=None):
        super().__init__()
        self.vertices = [None] * vertices
        if grid_dims:
            self[GRID_DIMS_PROPERTY] = ",".join(grid_dims)


@pytest.fixture
def cube():
    """A ``(time, y, x)`` dataset with two variables and a 2-D coordinate."""
    rng = np.random.default_rng(0)
    return xr.Dataset(
        {
            "sst": (("time", "y", "x"), rng.random((NT, NY, NX))),
            "ssh": (("time", "y", "x"), rng.random((NT, NY, NX))),
        },
        coords={
            "time": np.arange(float(NT)),
            "y": np.linspace(-10.0, 10.0, NY),
            "x": np.arange(float(NX)),
            "area": (("y", "x"), rng.random((NY, NX))),
        },
    )


def fibonacci_points(n):
    """Longitudes and latitudes of ``n`` points evenly spread on the sphere."""
    i = np.arange(n) + 0.5
    lat = np.degrees(np.arcsin(1 - 2 * i / n))
    lon = (np.degrees(np.pi * (1 + 5**0.5) * i) % 360.0) - 180.0
    return lon, lat


def in_box(lon, lat, box, margin=0.0):
    """Mask of the points inside ``box`` shrunk by ``margin`` degrees."""
    west, east, south, north = box
    return (
        (lon > west + margin)
        & (lon < east - margin)
        & (lat > south + margin)
        & (lat < north - margin)
    )


@pytest.fixture
def cells():
    """A FESOM-like ``(time, depth, ncells)`` dataset with lon/lat(ncells)."""
    lon, lat = fibonacci_points(NCELLS)
    ocean = ~in_box(lon, lat, LAND)
    lon, lat = lon[ocean], lat[ocean]
    rng = np.random.default_rng(0)
    return xr.Dataset(
        {"thetao": (("time", "depth", "ncells"), rng.random((NT, 2, lon.size)))},
        coords={
            "time": np.arange(float(NT)),
            "depth": [5.0, 15.0],
            "lon": ("ncells", lon, {"units": "degrees_east"}),
            "lat": ("ncells", lat, {"units": "degrees_north"}),
        },
    )


def linked(dataset, **axes):
    """Grid node coordinates, as from ``get_grid_coords``, for ``X=name``..."""
    return {
        axis: {"name": name, "size": dataset[name].shape, "data": dataset[name]}
        for axis, name in axes.items()
    }


def sphere_area(lon, lat, triangles):
    """Total area of the flat 3-D triangles joining points on the unit sphere."""
    lon, lat = np.radians(lon), np.radians(lat)
    xyz = np.column_stack(
        [np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)]
    )
    a, b, c = (xyz[triangles[:, k]] for k in range(3))
    return 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1).sum()


# -- dataset ------------------------------------------------------------------


@pytest.mark.parametrize(
    "names, pattern",
    [
        (["ssh_1995-01.nc", "ssh_1995-02.nc"], "ssh_1995-0*.nc"),
        (["ssh_1995-01.nc", "ssh_1995-02.nc", "ssh_1996-11.nc"], "ssh_199*-*.nc"),
        (["sst_2000.nc", "sst_2001.nc", "sst_2010.nc", "sst_1999.nc"], "sst_*.nc"),
    ],
)
def test_find_common_name(names, pattern):
    assert find_common_name(names) == pattern


@pytest.mark.parametrize(
    "names, message",
    [
        (["data_01.nc", "data_02.zarr"], "formats do not match"),
        (["x.nc", "y.nc"], "Start of filename"),
        (["same.nc", "same.nc"], "do not match"),
    ],
)
def test_find_common_name_refuses(names, message):
    with pytest.raises(ValueError, match=message):
        find_common_name(names)


def test_dataset_engine():
    assert dataset_engine("a/b.zarr") == "zarr"
    assert dataset_engine("a/b.grib2") == "cfgrib"
    assert dataset_engine("a/b.nc") is None


def test_names(cube):
    assert variable_names(cube) == ["ssh", "sst"]
    assert coordinate_names(cube) == ["area", "time", "x", "y"]


# -- slicing ------------------------------------------------------------------


def test_slicing_round_trip(cube):
    slicing = encode_slicing_record("*", "y", slice(0, None, 2))
    slicing += encode_slicing_record("sst", "time", 3)
    slicing += encode_slicing_record("ssh", "time", 1)
    assert slicing == "*|y|0::2,sst|time|3,ssh|time|1,"
    assert parse_slicing(slicing, "sst") == {"y": slice(0, None, 2), "time": 3}
    indexers = build_indexers(cube, cube["sst"], slicing, "sst")
    assert indexers == {"y": slice(0, None, 2), "time": 3}


def test_slicing_key_resolves_a_coordinate_to_its_dims(cube):
    slicing = encode_slicing_record("*", "area", slice(1, 3))
    assert build_indexers(cube, cube["sst"], slicing, "sst") == {
        "y": slice(1, 3),
        "x": slice(1, 3),
    }


def test_merge_selector_combines_range_and_stride():
    assert merge_selector(slice(0, None, 2), slice(2, 8)) == slice(2, 8, 2)
    assert merge_selector(slice(2, 8), slice(0, None, 3)) == slice(2, 8, 3)
    assert merge_selector(slice(2, 8), 4) == 4


def test_index_and_value_ranges():
    assert clamp_index_range(5, 7, 2) == (2, 4)
    assert clamp_index_range(5, -3, 1) == (0, 1)
    values = np.linspace(-80.0, 80.0, 8)
    assert value_index_range(values, 40.0, -40.0) == (2, 5)
    # Bounds stored in single precision still keep the values they name.
    assert value_index_range(values, np.float32(values[2]), np.float32(values[5])) == (
        2,
        5,
    )
    assert value_index_range(values, 100.0, 200.0) is None


def test_format_coord_value():
    assert format_coord_value(np.datetime64("2000-01-02T03:04:05.6")) == (
        "2000-01-02T03:04:05"
    )
    assert format_coord_value(1 / 3) == "0.333333"
    assert format_coord_value("a") == "a"


def test_suggested_stride():
    assert suggested_stride([]) == 1
    assert suggested_stride([500, 4000]) == 1
    assert suggested_stride([1001, 4000]) == 2
    # One dimension of scattered points holds the whole surface.
    assert suggested_stride([126859]) == 1
    assert suggested_stride([3_000_000]) == 3


# -- grid ---------------------------------------------------------------------


@pytest.mark.parametrize("name", ["lon", "latitude", "x", "xc", "xi_rho", "y_rho"])
def test_surface_names(name):
    assert is_surface_name(name)


@pytest.mark.parametrize("name", ["index", "time", "depth"])
def test_not_surface_names(name):
    assert not is_surface_name(name)


def test_surface_dims(cube):
    assert get_surface_dims(cube) == ["y", "x"]


def test_unstructured_dims(cells, cube):
    assert unstructured_dims(cells) == ["ncells"]
    assert get_surface_dims(cells) == ["ncells"]
    assert unstructured_dims(cube) == []


def test_grid_dims_of_scattered_points(cells, cube):
    assert grid_dims(linked(cells, X="lon", Y="lat")) == ("ncells",)
    assert grid_dims(linked(cube, X="x", Y="y")) == ("y", "x")


def test_triangulate_points_in_the_plane():
    x, y = np.array([0.0, 1.0, 0.0, 1.0]), np.array([0.0, 0.0, 1.0, 1.0])
    triangles = triangulate_points(x, y)
    assert triangles.shape == (2, 3) and triangles.dtype == np.int32
    a, b, c = triangles.T
    area = (x[b] - x[a]) * (y[c] - y[a]) - (x[c] - x[a]) * (y[b] - y[a])
    assert np.all(area > 0)  # counter-clockwise: faces point up Z


@pytest.mark.parametrize("count", [2, 3])
def test_triangulate_points_in_a_line(count):
    x = np.arange(float(count))
    with pytest.raises(ValueError, match="cannot be triangulated"):
        triangulate_points(x, np.zeros(count))


def test_scattered_mesh_on_the_sphere_skips_land(cells):
    positions, triangles = scattered_mesh(linked(cells, X="lon", Y="lat"), "ncells")
    lon, lat = cells["lon"].values, cells["lat"].values
    np.testing.assert_array_equal(positions[:, 0], lon.astype(np.float32))
    np.testing.assert_array_equal(positions[:, 1], lat.astype(np.float32))
    assert not positions[:, 2].any()

    assert np.ptp(lon[triangles], axis=1).max() <= 180.0
    centroids = lon[triangles].mean(axis=1), lat[triangles].mean(axis=1)
    assert not in_box(*centroids, LAND, margin=4.0).any()
    # The ocean is covered, poles included, but for a seam along +/-180.
    ocean = 4 * np.pi * lon.size / NCELLS
    assert sphere_area(lon, lat, triangles) > 0.97 * ocean
    # Spacing on the sphere keeps the polar triangles a flat lon/lat drops.
    every = triangulate_points(lon, lat, geographic=True, max_edge=0)
    polar = [t[lat[t].min(axis=1) > 70.0] for t in (triangles, every)]
    assert sphere_area(lon, lat, polar[0]) > 0.99 * sphere_area(lon, lat, polar[1])


def test_triangulate_points_leaves_out_the_lid_of_a_cap():
    lon, lat = fibonacci_points(4000)
    lon, lat = lon[lat > 30.0], lat[lat > 30.0]
    triangles = triangulate_points(lon, lat, geographic=True, max_edge=0)
    cap = 2 * np.pi * (1 - np.sin(np.radians(30.0)))
    assert sphere_area(lon, lat, triangles) < 1.01 * cap


def test_scattered_mesh_in_the_plane():
    x, y = np.meshgrid(np.arange(5.0) * 1000.0, np.arange(4.0) * 1000.0)
    dataset = xr.Dataset(coords={"x": ("n", x.ravel()), "y": ("n", y.ravel())})
    positions, triangles = scattered_mesh(linked(dataset, X="x", Y="y"), "n")
    assert len(positions) == 20 and len(triangles) == 2 * 4 * 3


def test_scattered_mesh_takes_z_over_the_points_only(cells):
    cells["level"] = cells["thetao"].isel(time=0, depth=0)
    coords = linked(cells, X="lon", Y="lat", Z="level")
    positions, _ = scattered_mesh(coords, "ncells")
    np.testing.assert_allclose(positions[:, 2], cells["level"].values, rtol=1e-6)
    with pytest.raises(ValueError, match=r"spans \(time, depth, ncells\)"):
        scattered_mesh(linked(cells, X="lon", Y="lat", Z="thetao"), "ncells")
    with pytest.raises(ValueError, match="need an X and a Y"):
        scattered_mesh(linked(cells, X="lon", Z="lat"), "ncells")


def test_find_coord_matches():
    assert find_coord_matches(12, {"time": 5, "y": 3, "x": 4}) == [("y", "x")]
    assert find_coord_matches(7, {"y": 3, "x": 4}) == []


# -- fields -------------------------------------------------------------------


def test_field_to_point_values_follows_the_grid_dims():
    field = xr.DataArray(np.arange(6.0).reshape(2, 3), dims=("y", "x"))
    np.testing.assert_array_equal(
        field_to_point_values(field), [0.0, 3.0, 1.0, 4.0, 2.0, 5.0]
    )
    # The same values in (x, y) order land on the same vertices.
    np.testing.assert_array_equal(
        field_to_point_values(field.T, ("y", "x")), field_to_point_values(field)
    )


def test_field_range_ignores_missing_values():
    assert field_range(np.array([np.nan, 2.0, -1.0, np.inf])) == (-1.0, 2.0)
    assert field_range(np.array([np.nan])) == (0.0, 0.0)


def test_texture_field_error(cube):
    mesh = FakeMesh(NX * NY, ("y", "x"))
    assert texture_field_error(cube["sst"].isel(time=0), mesh) == ""
    assert "Animate Texture" in texture_field_error(cube["sst"], mesh)
    assert "vertices" in texture_field_error(cube["sst"].isel(time=0), FakeMesh(7))


def test_animation_dim_prefers_the_baked_grid_dims():
    data = xr.DataArray(np.zeros((3, 4, 3)), dims=("a", "b", "c"))
    # (a, b) and (b, c) both hold 12 values; without baked dims the first wins.
    assert animation_dim(data, FakeMesh(12)) == "c"
    assert animation_dim(data, FakeMesh(12, ("b", "c"))) == "a"
    assert animation_dim(data, FakeMesh(5)) is None


def test_animated_field_error(cube):
    mesh = FakeMesh(NX * NY, ("y", "x"))
    assert animated_field_error(cube["sst"], mesh) == ("time", "")
    dim, message = animated_field_error(cube["sst"].isel(time=0), mesh)
    assert dim is None and "Datacube Texture node" in message


def test_fields_over_scattered_points(cells):
    data = cells["thetao"]
    mesh = FakeMesh(cells.sizes["ncells"], ("ncells",))
    field = data.isel(time=1, depth=0)
    assert texture_field_error(field, mesh) == ""
    assert "Animate Texture" in texture_field_error(data.isel(depth=0), mesh)
    assert "Select" in texture_field_error(data, mesh)
    np.testing.assert_array_equal(
        field_to_point_values(field, ("ncells",)), field.values.astype(np.float32)
    )
    assert animated_field_error(data.isel(depth=0), mesh) == ("time", "")
    dim, message = animated_field_error(field, mesh)
    assert dim is None and "Datacube Texture node for a 1D field" in message
    assert "Select" in animated_field_error(data, mesh)[1]


def test_animation_frame_holds_the_ends(cube):
    data = cube["sst"]
    for frame, index in ((-2, 0), (2, 2), (99, NT - 1)):
        np.testing.assert_array_equal(
            animation_frame(data, "time", frame), data.isel(time=index)
        )


# -- volume -------------------------------------------------------------------


def test_axis_placement():
    assert axis_placement("x", [0.0, 2.0, 4.0]) == (0.0, 2.0, None, "")
    origin, step, take, _ = axis_placement("y", [4.0, 2.0, 0.0])
    assert (origin, step) == (0.0, 2.0)
    np.testing.assert_array_equal(take, [2, 1, 0])
    origin, step, take, note = axis_placement("x", [0.0, 1.0, 3.0, 6.0])
    assert (origin, step) == (0.0, 2.0)
    np.testing.assert_array_equal(take, [0, 1, 2, 3])  # 2 ties: the smaller
    assert "unevenly spaced" in note


def test_nearest_positions_in_any_order():
    values = np.array([3.0, 1.0, 2.0])
    np.testing.assert_array_equal(
        nearest_positions(values, np.array([1.1, 2.9])), [1, 0]
    )


def test_volume_layout_and_placement_key(cube):
    data = cube["sst"]
    layout = volume_layout(data, "NONE")
    assert layout == ("x", "y", "time", "")
    key = placement_key(data, layout)
    assert key == placement_key(-data, layout)  # values do not move voxels
    assert key != placement_key(data.isel(x=slice(0, 2)), layout)
    with pytest.raises(ValueError):
        volume_layout(data.isel(time=0), "AUTO")


def test_volume_layout_refuses_scattered_points(cells):
    with pytest.raises(ValueError, match="ncells holds scattered points"):
        volume_layout(cells["thetao"], "AUTO")


def test_clamp_frame():
    assert [clamp_frame(frame, 3) for frame in (-1, 0, 2, 5)] == [0, 0, 2, 2]
