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
from blendernc.core.grid import find_coord_matches, get_surface_dims, is_surface_name
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
    VERTICAL_DEPTH,
    VERTICAL_LEVELS,
    axis_placement,
    clamp_frame,
    depth_interpolation,
    frame_array,
    interpolate_levels,
    nearest_positions,
    placement_key,
    vertical_voxel_count,
    volume_layout,
    volume_placement,
)

NX, NY, NT = 4, 3, 5


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


# -- grid ---------------------------------------------------------------------


@pytest.mark.parametrize("name", ["lon", "latitude", "x", "xc", "xi_rho", "y_rho"])
def test_surface_names(name):
    assert is_surface_name(name)


@pytest.mark.parametrize("name", ["index", "time", "depth"])
def test_not_surface_names(name):
    assert not is_surface_name(name)


def test_surface_dims(cube):
    assert get_surface_dims(cube) == ["y", "x"]


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


UNEVEN_Z = np.array([0.0, 10.0, 50.0, 300.0])


XYZ = ("x", "y", "z", "")


def levels_field(z=UNEVEN_Z, **z_attrs):
    """A random ``(x, y, z)`` field on levels ``z``."""
    rng = np.random.default_rng(1)
    z_coord = xr.Variable("z", z, attrs=z_attrs)
    return xr.DataArray(
        rng.random((NX, NY, z.size)),
        dims=("x", "y", "z"),
        coords={"x": np.arange(float(NX)), "y": np.arange(float(NY)), "z": z_coord},
        name="temp",
    )


def interpolated(data, targets):
    """``data`` interpolated column by column onto heights ``targets``."""
    z = data["z"].values
    columns = data.values.reshape(-1, z.size)
    out = [np.interp(targets, z, column) for column in columns]
    return np.array(out).reshape(NX, NY, targets.size)


def test_vertical_voxel_count():
    assert vertical_voxel_count(UNEVEN_Z) == 8  # 31 at 10 m, capped at 2 x 4
    assert vertical_voxel_count(np.array([0.0, 1.0, 3.0])) == 4  # finest spacing
    tenths = np.array([0.0, 0.1, 0.2, 0.3, 0.6, 0.8, 1.1])  # 11.000000000000004
    assert vertical_voxel_count(tenths) == 12  # steps, not rounded up to 12
    assert vertical_voxel_count(UNEVEN_Z, requested=31) == 31  # above the cap
    assert vertical_voxel_count(UNEVEN_Z, requested=1) == 2


def test_depth_interpolation_in_any_order():
    lower, upper, weight = depth_interpolation(UNEVEN_Z, 31)  # steps of 10
    np.testing.assert_array_equal(lower[:7], [0, 1, 1, 1, 1, 2, 2])
    np.testing.assert_array_equal(upper[:7], [1, 2, 2, 2, 2, 3, 3])
    np.testing.assert_allclose(weight[:7], [0, 0, 0.25, 0.5, 0.75, 0, 0.04])
    assert (lower[-1], upper[-1], weight[-1]) == (2, 3, 1.0)
    lower, upper, weight = depth_interpolation(UNEVEN_Z[::-1].copy(), 31)
    np.testing.assert_array_equal(lower[:2], [3, 2])


def test_true_depth_interpolates_levels():
    data = levels_field()
    placement = volume_placement(data, XYZ)
    assert placement.origin[2] == 0.0
    assert placement.step[2] == pytest.approx(300.0 / 7)
    assert "resampled onto 8 even steps" in placement.notes[0]
    expected = interpolated(data, np.linspace(0.0, 300.0, 8))
    frame = frame_array(data, XYZ, placement=placement)
    np.testing.assert_allclose(frame, expected, rtol=1e-5)


def test_true_depth_turns_depth_around():
    data = levels_field(positive="down")
    placement = volume_placement(data, XYZ, VERTICAL_DEPTH, vertical_voxels=31)
    assert (placement.origin[2], placement.step[2]) == (-300.0, 10.0)
    expected = interpolated(data, np.linspace(0.0, 300.0, 31))[..., ::-1]
    frame = frame_array(data, XYZ, placement=placement)
    np.testing.assert_allclose(frame, expected, rtol=1e-5)


def test_one_voxel_per_level():
    data = levels_field()
    placement = volume_placement(data, XYZ, VERTICAL_LEVELS)
    assert (placement.origin[2], placement.step[2]) == (0.0, 1.0)
    assert placement.vertical is None
    assert "one voxel per level" in placement.notes[0]
    repeated = levels_field(np.array([0.0, 10.0, 10.0, 300.0]))
    assert volume_placement(repeated, XYZ).vertical is None  # cannot interpolate


def test_missing_levels_are_not_blended():
    """A missing level is filled after interpolating: the data stops half way."""
    data = levels_field()
    data[..., 3] = np.nan
    placement = volume_placement(data, XYZ, vertical_voxels=31)
    frame = frame_array(data, XYZ, background=-1.0, placement=placement)
    column = frame[0, 0]
    np.testing.assert_allclose(column[5:18], data.values[0, 0, 2], rtol=1e-6)
    np.testing.assert_array_equal(column[18:], -1.0)  # above 175 m: past half way


def test_interpolate_levels_uses_the_nearer_level_next_to_nan():
    array = np.array([[[1.0, np.nan]]], dtype=np.float32)
    lower, upper = np.array([0, 0, 0]), np.array([1, 1, 1])
    weight = np.array([0.25, 0.5, 0.75], dtype=np.float32)
    result = interpolate_levels(array, lower, upper, weight)
    np.testing.assert_array_equal(result[0, 0], [1.0, 1.0, np.nan])


def test_placement_key_follows_vertical_settings():
    data = levels_field()
    key = placement_key(data, XYZ)
    assert key == placement_key(data, XYZ, VERTICAL_DEPTH, 0)
    assert key != placement_key(data, XYZ, VERTICAL_LEVELS, 0)
    assert key != placement_key(data, XYZ, VERTICAL_DEPTH, 31)


def test_clamp_frame():
    assert [clamp_frame(frame, 3) for frame in (-1, 0, 2, 5)] == [0, 0, 2, 2]
