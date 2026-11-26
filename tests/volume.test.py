"""Bake Datacube Volume nodes from synthetic xarray datasets.

Four datasets are generated on the fly with a random-noise variable:

* ``(X, Y)``: refused, a volume needs three dimensions.
* ``(X, Y, Z)``: one static volume, Z vertical.
* ``(X, Y, time)``: a static space-time cube, time vertical; or, with
  "Animate along" set to time, a one-voxel-thick slab per frame.
* ``(X, Y, Z, time)``: a volume animated along time, either as a VDB
  sequence ("Bake all frames") or one file per shown frame ("Current frame").

Variants of ``(X, Y, Z)`` check the placement: a descending, an unevenly
spaced and a curvilinear horizontal axis, 2-D coordinates that are in fact
rectilinear, a depth axis marked ``positive = "down"`` and uneven levels,
placed at their true depth or one voxel per level.
A copy of ``(X, Y, Z)`` with a second variable checks that changing the
variable only refreshes the values. Whatever the bake, a volume the user
moved, rotated or scaled keeps that transform on top of its placement.

The VDB files are read back with the ``openvdb`` module that ships with
Blender and compared to the variable.
"""

import glob
import os
import shutil
import sys
import tempfile
import unittest

import bpy
import numpy as np
import openvdb
import xarray as xr
from mathutils import Vector

from blendernc.core.fields import RANGE_PROPERTIES
from blendernc.core.volume import mask_grid_name, nearest_positions, placement_key
from blendernc.handlers import bNC_update_volumes
from blendernc.node_utils import create_blenderncnodetree
from blendernc.utils import get_dataset
from blendernc.volume_utils import UNSAVED_WARNING, get_animate_dims, vdb_directory

NX, NY, NZ, NT = 12, 8, 4, 5
VARIABLE = "noise"
OTHER = "other"
X_VALUES = np.linspace(0.0, 360.0, NX, endpoint=False)
Y_VALUES = np.linspace(-80.0, 80.0, NY)
Z_VALUES = np.linspace(0.0, 300.0, NZ)
# Rotated grid: longitude and latitude both change along both dimensions.
ANGLE = np.radians(30.0)


def make_dataset(path, with_level=False, with_time=False, seed=0):
    """Write a netCDF file with a noise variable and return the dataset."""
    rng = np.random.default_rng(seed)
    coords = {"X": ("X", X_VALUES), "Y": ("Y", Y_VALUES)}
    dims, shape = ["Y", "X"], [NY, NX]
    if with_level:
        coords["Z"] = ("Z", np.linspace(0.0, 300.0, NZ))
        dims.insert(0, "Z")
        shape.insert(0, NZ)
    if with_time:
        start = np.datetime64("2000-01-01")
        coords["time"] = ("time", start + np.arange(NT).astype("timedelta64[D]"))
        dims.insert(0, "time")
        shape.insert(0, NT)
    values = rng.standard_normal(shape)
    dataset = xr.Dataset({VARIABLE: (dims, values)}, coords=coords)
    dataset.to_netcdf(path)
    return dataset


def make_xyz_variant(
    path, x=X_VALUES, y=Y_VALUES, z=Z_VALUES, z_attrs=None, coords_2d=None, land=0
):
    """Write an ``(X, Y, Z)`` noise dataset with the given axes; return it.

    ``coords_2d`` maps extra coordinate names to ``(Y, X)`` arrays, such as
    a curvilinear longitude and latitude. The first ``land`` X columns are
    missing, written as the netCDF fill value.
    """
    rng = np.random.default_rng(3)
    coords = {"X": ("X", x), "Y": ("Y", y), "Z": ("Z", z, z_attrs or {})}
    for name, values in (coords_2d or {}).items():
        coords[name] = (("Y", "X"), values)
    values = rng.standard_normal((len(z), len(y), len(x)))
    values[:, :, :land] = np.nan
    dataset = xr.Dataset({VARIABLE: (("Z", "Y", "X"), values)}, coords=coords)
    dataset.to_netcdf(path, encoding={VARIABLE: {"_FillValue": -999.0}})
    return dataset


def rotated_grid():
    """Longitude and latitude of a grid rotated by ``ANGLE``, unit spacing."""
    j, i = np.meshgrid(np.arange(NY), np.arange(NX), indexing="ij")
    lon = 10.0 + i * np.cos(ANGLE) - j * np.sin(ANGLE)
    lat = 20.0 + i * np.sin(ANGLE) + j * np.cos(ANGLE)
    return lon, lat


def read_grid(path, shape, name=VARIABLE):
    """Read the grid ``name`` from a VDB file into an array of ``shape``."""
    grid = openvdb.read(path, name)
    array = np.zeros(shape, dtype=np.float32)
    grid.copyToArray(array)
    return array


class TestDatacubeVolume(unittest.TestCase):
    """Bake volumes from generated datasets and check files and objects."""

    @classmethod
    def setUpClass(cls):
        """Generate the four netCDF files in a temporary directory."""
        cls.tmpdir = tempfile.mkdtemp(prefix="blendernc_volume_")
        cls.files, cls.datasets = {}, {}
        for key, with_level, with_time in (
            ("xy", False, False),
            ("xyz", True, False),
            ("xyt", False, True),
            ("xyzt", True, True),
        ):
            path = os.path.join(cls.tmpdir, f"{key}.nc")
            cls.datasets[key] = make_dataset(path, with_level, with_time)
            cls.files[key] = path
        lon, lat = rotated_grid()
        rect_lon, rect_lat = np.meshgrid(X_VALUES, Y_VALUES)
        uneven = np.cumsum(np.arange(1.0, NX + 1.0)) - 1.0  # steps 2, 3, 4, ...
        for key, kwargs in (
            ("desc_y", {"y": Y_VALUES[::-1].copy()}),
            ("uneven_x", {"x": uneven}),
            ("curvilinear", {"coords_2d": {"lon": lon, "lat": lat}}),
            ("rect_2d", {"coords_2d": {"lon": rect_lon, "lat": rect_lat}}),
            ("depth", {"z_attrs": {"positive": "down", "units": "m"}}),
            ("uneven_z", {"z": np.array([0.0, 10.0, 50.0, 300.0])}),
            ("land", {"land": 3}),
        ):
            path = os.path.join(cls.tmpdir, f"{key}.nc")
            cls.datasets[key] = make_xyz_variant(path, **kwargs)
            cls.files[key] = path
        path = os.path.join(cls.tmpdir, "two_vars.nc")
        xyz = cls.datasets["xyz"]
        cls.datasets["two_vars"] = xyz.assign({OTHER: 5.0 - 2.0 * xyz[VARIABLE]})
        cls.datasets["two_vars"].to_netcdf(path)
        cls.files["two_vars"] = path

    @classmethod
    def tearDownClass(cls):
        """Remove the netCDF and VDB files."""
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def setUp(self):
        """Give every test its own node tree, object name and VDB folder."""
        self.tree = create_blenderncnodetree(f"BNC_VOL_{self._testMethodName}")
        self.obj_name = f"Volume_{self._testMethodName}"
        self.vdb_dir = os.path.join(self.tmpdir, self._testMethodName)
        bpy.context.scene.frame_set(0)

    def tearDown(self):
        """Drop the node tree, the volume object and its datablock."""
        obj = bpy.data.objects.get(self.obj_name)
        if obj is not None:
            volume = obj.data
            bpy.data.objects.remove(obj)
            bpy.data.volumes.remove(volume)
        bpy.data.node_groups.remove(self.tree)

    # -- pipeline -----------------------------------------------------------

    def build(self, key, animate_dim=None, frame_mode=None, select_z=None):
        """Link Import -> Variable (-> Select) -> Volume; return the volume node."""
        tree = self.tree
        import_node = tree.nodes.new("BlenderNCNodeImport")
        variable = self.variable = tree.nodes.new("BlenderNCNodeVariable")
        node = self.node = tree.nodes.new("BlenderNCNodeVolume")
        import_node.datacube_file = self.files[key]
        datacube = "xarray datacube"
        tree.links.new(import_node.outputs[datacube], variable.inputs[datacube])
        self.assertIsNotNone(get_dataset(import_node.BNC_datastructs[0]))
        variable.datacube_vars = VARIABLE
        source = variable.outputs[VARIABLE]
        if select_z is not None:
            self.select = tree.nodes.new("BlenderNCNodeSelect")
            tree.links.new(source, self.select.inputs["Variable"])
            self.select.datacube_coords = "Z"
            self.select.index = select_z
            source = self.select.outputs["Variable"]
        tree.links.new(source, node.inputs["Variable"])
        node.volume_obj_name = self.obj_name
        node.vdb_dir = self.vdb_dir
        if frame_mode:
            node.frame_mode = frame_mode
        if animate_dim:
            node.animate_dim = animate_dim
        node.update()
        return node

    def bake(self):
        """Run the bake operator on the volume node; return the object."""
        bpy.ops.blendernc.create_volume(
            node_name=self.node.name, node_tree=self.tree.name
        )
        return bpy.data.objects[self.obj_name]

    def vdb_files(self):
        """VDB files written by the volume node, sorted by name."""
        return sorted(glob.glob(os.path.join(self.vdb_dir, "*", "*.vdb")))

    def expected(self, key, vertical, variable=VARIABLE, **isel):
        """``variable`` as an ``(X, Y, vertical)`` array, after ``isel``."""
        data = self.datasets[key][variable].isel(isel)
        if vertical:
            return data.transpose("X", "Y", vertical).values
        return data.transpose("X", "Y").values[..., np.newaxis]

    # -- static volumes -----------------------------------------------------

    def test_xyz_static_volume(self):
        """(X, Y, Z) writes one VDB with the field, placed on X and Y."""
        self.build("xyz")
        obj = self.bake()
        files = self.vdb_files()
        self.assertEqual(len(files), 1)
        self.assertFalse(obj.data.is_sequence)
        np.testing.assert_allclose(
            read_grid(files[0], (NX, NY, NZ)), self.expected("xyz", "Z"), rtol=1e-6
        )
        np.testing.assert_allclose(obj.location, (0.0, -80.0, 0.0), atol=1e-5)
        # Z is evenly spaced, so it sets the voxel height as X and Y do.
        np.testing.assert_allclose(obj.scale, (30.0, 160.0 / 7, 100.0), rtol=1e-5)
        data = self.datasets["xyz"][VARIABLE]
        self.assertAlmostEqual(obj[RANGE_PROPERTIES[0]], float(data.min()), places=5)
        self.assertAlmostEqual(obj[RANGE_PROPERTIES[1]], float(data.max()), places=5)
        self.assertEqual(self.node.message, "")
        self.assertEqual(self.node.note, "")
        self.assertEqual(self.node.outputs["Object"].default_value, obj)

    def test_xyt_space_time_cube(self):
        """(X, Y, time) becomes one static volume with time running upwards."""
        self.build("xyt")
        obj = self.bake()
        files = self.vdb_files()
        self.assertEqual(len(files), 1)
        self.assertFalse(obj.data.is_sequence)
        np.testing.assert_allclose(
            read_grid(files[0], (NX, NY, NT)), self.expected("xyt", "time"), rtol=1e-6
        )

    def test_vertical_scale_stretches_object(self):
        """The vertical scale multiplies the Z spacing, without a rebake."""
        self.build("xyz")
        obj = self.bake()
        token = self.node.bake_token
        self.node.vertical_scale = 0.25
        self.assertAlmostEqual(obj.scale.z, 100.0 * 0.25, places=4)
        self.assertAlmostEqual(obj.location.z, 0.0)
        self.assertEqual(self.node.bake_token, token)

    def test_density_material(self):
        """The volume gets a density-only material reading the grid."""
        self.build("xyz")
        obj = self.bake()
        material = obj.data.materials[0]
        nodes = material.node_tree.nodes
        self.assertEqual(nodes["Attribute"].attribute_name, VARIABLE)
        principled = nodes["Principled Volume"]
        density = principled.inputs["Density"]
        self.assertTrue(density.is_linked)
        self.assertEqual(density.links[0].from_node.bl_idname, "ShaderNodeMapRange")
        mask = principled.inputs["Density Attribute"].default_value
        self.assertEqual(mask, mask_grid_name(VARIABLE))
        output = nodes["Material Output"].inputs["Volume"]
        self.assertEqual(output.links[0].from_node, nodes["Principled Volume"])
        for key in ("Attribute", "Attribute.001", "Attribute.002"):
            self.assertTrue(nodes[key].outputs["Factor"].is_linked, key)

    # -- animated volumes ---------------------------------------------------

    def test_xyzt_sequence(self):
        """(X, Y, Z, time) bakes one VDB per time step as a volume sequence."""
        self.build("xyzt")
        obj = self.bake()
        files = self.vdb_files()
        self.assertEqual(len(files), NT)
        volume = obj.data
        self.assertTrue(volume.is_sequence)
        self.assertEqual(volume.frame_duration, NT)
        self.assertEqual(volume.frame_start, 0)
        for index, path in enumerate(files):
            np.testing.assert_allclose(
                read_grid(path, (NX, NY, NZ)),
                self.expected("xyzt", "Z", time=index),
                rtol=1e-6,
            )

    def test_xyzt_live_frame(self):
        """ "Current frame" keeps one file and follows the scene frame."""
        self.build("xyzt", frame_mode="LIVE")
        obj = self.bake()
        self.assertEqual(len(self.vdb_files()), 1)
        self.assertFalse(obj.data.is_sequence)

        scene = bpy.context.scene
        scene.frame_current = 2
        bNC_update_volumes(scene)
        files = self.vdb_files()
        self.assertEqual(len(files), 1)
        self.assertEqual(bpy.path.abspath(obj.data.filepath), files[0])
        np.testing.assert_allclose(
            read_grid(files[0], (NX, NY, NZ)),
            self.expected("xyzt", "Z", time=2),
            rtol=1e-6,
        )
        scene.frame_current = 99  # clamps to the last time step
        bNC_update_volumes(scene)
        np.testing.assert_allclose(
            read_grid(self.vdb_files()[0], (NX, NY, NZ)),
            self.expected("xyzt", "Z", time=NT - 1),
            rtol=1e-6,
        )

    def test_xyt_animated_slab(self):
        """Animating (X, Y, time) along time gives one-voxel-thick frames."""
        self.build("xyt", animate_dim="time")
        obj = self.bake()
        files = self.vdb_files()
        self.assertEqual(len(files), NT)
        self.assertTrue(obj.data.is_sequence)
        np.testing.assert_allclose(
            read_grid(files[3], (NX, NY, 1)),
            self.expected("xyt", "", time=3),
            rtol=1e-6,
        )

    # -- following the tree -------------------------------------------------

    def move(self, obj):
        """Move and stretch ``obj`` as a user would; return its transform."""
        obj.location = (5.0, 6.0, 7.0)
        obj.scale = (1.0, 2.0, 3.0)
        return self.transform(obj)

    def transform(self, obj):
        """``obj``'s location and scale as one tuple."""
        return (*obj.location, *obj.scale)

    def test_select_change_refreshes_values(self):
        """Another level of a Select rewrites the values in place."""
        self.build("xyzt", select_z=0)
        obj = self.bake()
        token = self.node.bake_token
        moved = self.move(obj)
        self.select.index = 2  # (time, Y, X) -> space-time cube of level 2
        self.assertEqual(self.node.bake_token, token + 1)
        np.testing.assert_allclose(self.transform(obj), moved)
        files = self.vdb_files()
        self.assertEqual(len(files), 1)
        np.testing.assert_allclose(
            read_grid(files[0], (NX, NY, NT)),
            self.expected("xyzt", "time", Z=2),
            rtol=1e-6,
        )

    def test_variable_change_refreshes_values(self):
        """Another variable keeps the placement, and so does the button."""
        from blendernc import volume_utils

        self.build("two_vars")
        obj = self.bake()
        moved = self.move(obj)
        computed = []
        original = volume_utils.volume_placement

        def counting(*args, **kwargs):
            computed.append(args)
            return original(*args, **kwargs)

        volume_utils.volume_placement = counting
        try:
            self.variable.datacube_vars = OTHER
            self.tree.links.new(
                self.variable.outputs[OTHER], self.node.inputs["Variable"]
            )
        finally:
            volume_utils.volume_placement = original
        self.assertEqual(computed, [])
        np.testing.assert_allclose(self.transform(obj), moved)
        self.assertEqual(obj.data.materials[0].name, f"{OTHER} volume")
        self.assertEqual(len(obj.data.materials), 1)
        (path,) = self.vdb_files()
        np.testing.assert_allclose(
            read_grid(path, (NX, NY, NZ), OTHER),
            self.expected("two_vars", "Z", OTHER),
            rtol=1e-6,
        )
        self.bake()
        self.assertEqual(self.transform(obj), moved)

    def test_variable_change_without_lock_takes_its_range(self):
        """With "Lock range" off the refreshed volume gets the new range."""
        settings = bpy.context.scene.BlenderNC_Settings
        locked = settings.lock_range
        self.build("two_vars")
        obj = self.bake()
        try:
            settings.lock_range = False
            self.variable.datacube_vars = OTHER
            self.tree.links.new(
                self.variable.outputs[OTHER], self.node.inputs["Variable"]
            )
        finally:
            settings.lock_range = locked
        data = self.datasets["two_vars"][OTHER]
        self.assertAlmostEqual(obj[RANGE_PROPERTIES[0]], float(data.min()), places=5)
        self.assertAlmostEqual(obj[RANGE_PROPERTIES[1]], float(data.max()), places=5)

    def insert(self, bl_idname, coord, **settings):
        """Put a node on ``coord`` between the variable and the volume."""
        node = self.tree.nodes.new(bl_idname)
        self.tree.links.new(self.variable.outputs[VARIABLE], node.inputs["Variable"])
        node.datacube_coords = coord
        for name, value in settings.items():
            setattr(node, name, value)
        self.tree.links.new(node.outputs["Variable"], self.node.inputs["Variable"])
        return node

    def test_slice_keeps_user_transform(self):
        """A Slice along X lands where that part of the moved volume was."""
        self.build("xyz")
        obj = self.bake()
        self.move(obj)
        obj.rotation_euler.z = np.pi / 2
        third_column = obj.matrix_basis @ Vector((2.0, 0.0, 0.0))
        self.insert("BlenderNCNodeSlice", "X", first=2, last=7)
        np.testing.assert_allclose(obj.matrix_basis.translation, third_column)
        np.testing.assert_allclose(obj.scale, (1.0, 2.0, 3.0))
        self.assertAlmostEqual(obj.rotation_euler.z, np.pi / 2, places=6)
        (path,) = self.vdb_files()
        np.testing.assert_allclose(
            read_grid(path, (6, NY, NZ)),
            self.expected("xyz", "Z", X=slice(2, 8)),
            rtol=1e-6,
        )

    def test_subsample_keeps_user_scale(self):
        """Twice the voxel size along X doubles the user's X scale."""
        self.build("xyz")
        obj = self.bake()
        self.move(obj)
        self.insert("BlenderNCNodeSubsample", "X", step=2)
        np.testing.assert_allclose(obj.location, (5.0, 6.0, 7.0))
        np.testing.assert_allclose(obj.scale, (2.0, 2.0, 3.0))
        (path,) = self.vdb_files()
        np.testing.assert_allclose(
            read_grid(path, (NX // 2, NY, NZ)),
            self.expected("xyz", "Z", X=slice(0, None, 2)),
            rtol=1e-6,
        )

    def test_adding_select_keeps_user_transform(self):
        """Selecting one time step of an animated volume moves nothing."""
        self.build("xyzt", frame_mode="LIVE")
        obj = self.bake()
        obj.scale = (0.014,) * 3
        obj.location = (0.0, 0.0, 0.0)
        moved = self.transform(obj)
        select = self.insert("BlenderNCNodeSelect", "time")
        self.assertEqual(self.transform(obj), moved)
        select.index = 3
        self.assertEqual(self.transform(obj), moved)
        self.assertEqual(len(self.vdb_files()), 1)

    def test_vertical_scale_keeps_user_transform(self):
        """The vertical scale stretches about the coordinate's zero."""
        self.build("depth")  # Z from 0 down to -300: zero is the top level
        obj = self.bake()
        self.move(obj)
        top = obj.matrix_basis @ Vector((0.0, 0.0, NZ - 1.0))
        self.node.vertical_scale = 0.25
        np.testing.assert_allclose(obj.matrix_basis @ Vector((0, 0, NZ - 1)), top)
        np.testing.assert_allclose(obj.scale, (1.0, 2.0, 3.0 * 0.25))

    def test_volume_baked_before_placements_were_recorded(self):
        """Without a recorded placement the object is placed afresh, once."""
        self.build("xyz")
        obj = self.bake()
        self.move(obj)
        self.node.placed_scale = (0.0, 0.0, 0.0)  # as in an older file
        self.bake()
        np.testing.assert_allclose(obj.location, (0.0, -80.0, 0.0), atol=1e-5)
        np.testing.assert_allclose(obj.scale, (30.0, 160.0 / 7, 100.0), rtol=1e-5)
        moved = self.move(obj)
        self.bake()
        self.assertEqual(self.transform(obj), moved)

    def test_placement_key_follows_coordinates_only(self):
        """Values, frames and a dropped dimension leave the key unchanged."""
        data = self.datasets["xyzt"][VARIABLE]
        layout = ("X", "Y", "Z", "time")
        key = placement_key(data, layout)
        self.assertEqual(key, placement_key(-data, layout))
        self.assertEqual(key, placement_key(data.isel(time=slice(0, 2)), layout))
        self.assertNotEqual(key, placement_key(data.isel(X=slice(0, 6)), layout))
        moved = data.assign_coords(Z=data["Z"] * 2.0)
        self.assertNotEqual(key, placement_key(moved, layout))
        static = ("X", "Y", "Z", None)
        self.assertEqual(
            placement_key(data.isel(time=0), static),
            placement_key(data.isel(time=3), static),
        )

    # -- placement ------------------------------------------------------------

    def read_single(self, key, nz=NZ):
        """Bake dataset ``key`` and read its only VDB file, ``nz`` voxels high."""
        self.build(key)
        obj = self.bake()
        files = self.vdb_files()
        self.assertEqual(len(files), 1)
        return obj, read_grid(files[0], (NX, NY, nz))

    def uneven_levels(self, nz):
        """The ``uneven_z`` field interpolated onto ``nz`` even heights."""
        z = self.datasets["uneven_z"]["Z"].values
        targets = np.linspace(z.min(), z.max(), nz)
        return np.apply_along_axis(
            lambda column: np.interp(targets, z, column),
            2,
            self.expected("uneven_z", "Z"),
        )

    def test_descending_y_is_flipped(self):
        """A descending Y keeps a positive scale: the voxels are reversed."""
        obj, grid = self.read_single("desc_y")
        expected = self.expected("desc_y", "Z")[:, ::-1, :]
        np.testing.assert_allclose(grid, expected, rtol=1e-6)
        np.testing.assert_allclose(obj.location[:2], (0.0, -80.0), atol=1e-5)
        np.testing.assert_allclose(obj.scale[:2], (30.0, 160.0 / 7), rtol=1e-5)
        self.assertEqual(self.node.note, "")

    def test_uneven_x_is_resampled(self):
        """Uneven X is resampled by nearest neighbour and the node says so."""
        obj, grid = self.read_single("uneven_x")
        x = self.datasets["uneven_x"]["X"].values
        targets = np.linspace(x.min(), x.max(), NX)
        nearest = [int(np.argmin(np.abs(x - t))) for t in targets]  # brute force
        expected = self.expected("uneven_x", "Z")[nearest]
        np.testing.assert_allclose(grid, expected, rtol=1e-6)
        self.assertAlmostEqual(obj.scale.x, (x.max() - x.min()) / (NX - 1), places=4)
        self.assertIn("X is unevenly spaced", self.node.note)

    def test_nearest_positions_in_any_order(self):
        """The nearest value wins whatever the order of the values."""
        values = np.array([5.0, 0.0, 9.0, 2.0])
        targets = np.array([-1.0, 1.0, 1.1, 4.0, 8.0, 20.0])
        np.testing.assert_array_equal(
            nearest_positions(values, targets), [1, 1, 3, 0, 2, 2]
        )

    def test_curvilinear_is_resampled(self):
        """A rotated grid is resampled onto a regular one covering it."""
        obj, grid = self.read_single("curvilinear")
        dataset = self.datasets["curvilinear"]
        lon, lat = dataset["lon"].values, dataset["lat"].values
        self.assertIn("lon/lat are curvilinear", self.node.note)
        np.testing.assert_allclose(obj.location[:2], (lon.min(), lat.min()), atol=1e-4)
        step_x = (lon.max() - lon.min()) / (NX - 1)
        self.assertAlmostEqual(obj.scale.x, step_x, places=4)

        # The bounding box corner at (min lon, min lat) lies outside the data.
        (path,) = self.vdb_files()
        mask = read_grid(path, (NX, NY, NZ), mask_grid_name(VARIABLE))
        np.testing.assert_array_equal(mask[0, 0], 0.0)
        np.testing.assert_array_equal(mask[NX // 2, NY // 2], 1.0)
        # Inside, each voxel column is the nearest source column.
        values = dataset[VARIABLE].transpose("X", "Y", "Z").values
        tx = np.linspace(lon.min(), lon.max(), NX)
        ty = np.linspace(lat.min(), lat.max(), NY)
        src = np.column_stack([lon.T.ravel(), lat.T.ravel()])  # (X, Y) order
        ix, iy = NX // 2, NY // 2
        nearest = np.argmin(np.hypot(*(src - (tx[ix], ty[iy])).T))
        np.testing.assert_allclose(
            grid[ix, iy], values.reshape(NX * NY, NZ)[nearest], rtol=1e-6
        )

    def test_rectilinear_2d_coords_are_not_resampled(self):
        """2-D lon/lat that only vary along their own axis place voxels directly."""
        obj, grid = self.read_single("rect_2d")
        np.testing.assert_allclose(grid, self.expected("rect_2d", "Z"), rtol=1e-6)
        np.testing.assert_allclose(obj.scale[:2], (30.0, 160.0 / 7), rtol=1e-5)
        self.assertEqual(self.node.note, "")

    def test_depth_positive_down_goes_below_zero(self):
        """``positive = "down"`` puts the deepest level lowest, below zero."""
        obj, grid = self.read_single("depth")
        expected = self.expected("depth", "Z")[:, :, ::-1]
        np.testing.assert_allclose(grid, expected, rtol=1e-6)
        self.assertAlmostEqual(obj.location.z, -300.0, places=4)
        self.assertAlmostEqual(obj.scale.z, 100.0, places=4)

    def test_missing_data_is_masked(self):
        """The mask marks the data; values reach two voxels into missing data.

        The first three X columns are missing: the mask is 0 there, columns
        2 and 1 copy column 3 (their only valid neighbour), and column 0
        stays empty, at the zero background.
        """
        self.build("land")
        self.bake()
        (path,) = self.vdb_files()
        values = self.expected("land", "Z")
        mask_name = mask_grid_name(VARIABLE)
        for name in (VARIABLE, mask_name):
            self.assertEqual(openvdb.read(path, name).background, 0.0, name)
        mask = read_grid(path, (NX, NY, NZ), mask_name)
        np.testing.assert_array_equal(mask, np.isfinite(values))
        array = read_grid(path, (NX, NY, NZ))
        np.testing.assert_allclose(array[3:], values[3:], rtol=1e-6)
        for column in (2, 1):
            np.testing.assert_allclose(array[column], values[3], rtol=1e-6)
        np.testing.assert_array_equal(array[0], 0.0)
        grid = openvdb.read(path, VARIABLE)
        self.assertEqual(grid.activeVoxelCount(), (NX - 1) * NY * NZ)
        lowest = np.unravel_index(np.nanargmin(values), values.shape)
        self.assertTrue(grid.getConstAccessor().isValueOn(tuple(map(int, lowest))))

    def test_uneven_levels_at_true_depth(self):
        """Uneven Z levels are interpolated onto at most twice as many steps."""
        obj, grid = self.read_single("uneven_z", nz=2 * NZ)
        expected = self.uneven_levels(2 * NZ)
        np.testing.assert_allclose(grid, expected, rtol=1e-5, atol=1e-5)
        self.assertAlmostEqual(obj.location.z, 0.0)
        self.assertAlmostEqual(obj.scale.z, 300.0 / 7, places=4)
        self.assertIn("Z is unevenly spaced", self.node.note)
        self.assertIn("8 even steps", self.node.note)

    def test_vertical_voxels_set_the_steps(self):
        """Vertical voxels sets the number of steps; the node rebakes itself."""
        obj, _ = self.read_single("uneven_z", nz=2 * NZ)
        self.node.vertical_voxels = 31
        (path,) = self.vdb_files()
        np.testing.assert_allclose(
            read_grid(path, (NX, NY, 31)), self.uneven_levels(31), rtol=1e-5, atol=1e-5
        )
        self.assertAlmostEqual(obj.scale.z, 10.0, places=4)
        self.assertIn("31 even steps", self.node.note)

    def test_uneven_levels_one_voxel_per_level(self):
        """ "One voxel per level" stacks uneven Z levels, with a note on the node."""
        obj, _ = self.read_single("uneven_z", nz=2 * NZ)
        self.node.vertical_mode = "LEVELS"  # rebakes
        (path,) = self.vdb_files()
        np.testing.assert_allclose(
            read_grid(path, (NX, NY, NZ)), self.expected("uneven_z", "Z"), rtol=1e-6
        )
        self.assertAlmostEqual(obj.location.z, 0.0)
        self.assertAlmostEqual(obj.scale.z, 1.0)
        self.assertIn("one voxel per level", self.node.note)

    def test_live_frames_reuse_the_curvilinear_resampling(self):
        """Current-frame files match the frames of a full sequence bake."""
        from blendernc import volume_utils

        self.build("curvilinear", animate_dim="Z")
        self.bake()
        reference = [read_grid(path, (NX, NY, 1)) for path in self.vdb_files()]
        self.assertEqual(len(reference), NZ)

        self.node.frame_mode = "LIVE"  # rebakes the frame shown, frame 0
        scene = bpy.context.scene
        for frame, forget in ((2, False), (3, True)):
            if forget:  # as after reopening the file
                volume_utils._PLACEMENTS.clear()
            scene.frame_current = frame
            bNC_update_volumes(scene)
            (path,) = self.vdb_files()
            np.testing.assert_allclose(
                read_grid(path, (NX, NY, 1)), reference[frame], rtol=1e-6
            )

    # -- range, dims and files ------------------------------------------------

    def test_lock_range_keeps_stored_range(self):
        """Under "Lock range" a rebake keeps the range stored on the object."""
        settings = bpy.context.scene.BlenderNC_Settings
        low, high = RANGE_PROPERTIES
        self.build("xyz")
        obj = self.bake()
        obj[low], obj[high] = -10.0, 10.0
        try:
            settings.lock_range = True
            self.bake()
            self.assertEqual((obj[low], obj[high]), (-10.0, 10.0))
            settings.lock_range = False
            self.bake()
            data = self.datasets["xyz"][VARIABLE]
            self.assertAlmostEqual(obj[low], float(data.min()), places=5)
        finally:
            settings.lock_range = True

    def test_animate_dims_follow_slicing(self):
        """A dimension dropped by a Select node is not offered for animation."""
        self.build("xyzt", select_z=1)
        names = [item[0] for item in get_animate_dims(self.node, bpy.context)]
        self.assertNotIn("Z", names)
        self.assertIn("time", names)

    def test_deleting_node_keeps_files_a_volume_reads(self):
        """The baked Volume still reads the files, so they stay."""
        self.build("xyz")
        self.bake()
        directory = vdb_directory(self.node, create=False)
        self.tree.nodes.remove(self.node)
        self.assertTrue(os.path.isdir(directory))

    def test_deleting_node_removes_unused_files(self):
        """Once no Volume reads the folder, deleting the node removes it."""
        self.build("xyz")
        obj = self.bake()
        directory = vdb_directory(self.node, create=False)
        volume = obj.data
        bpy.data.objects.remove(obj)
        bpy.data.volumes.remove(volume)
        self.tree.nodes.remove(self.node)
        self.assertFalse(os.path.exists(directory))

    def test_unsaved_file_warns(self):
        """With a '//' folder in an unsaved file the node warns about it."""
        self.assertEqual(bpy.data.filepath, "", "tests run without a .blend file")
        self.build("xyz")
        self.node.vdb_dir = "//blendernc_vdb/"
        self.bake()
        directory = vdb_directory(self.node, create=False)
        try:
            self.assertEqual(self.node.warning, UNSAVED_WARNING)
            self.assertTrue(directory.startswith(bpy.app.tempdir))
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    # -- refused fields -----------------------------------------------------

    def test_xy_refused(self):
        """A 2-D field is refused with a pointer to the Texture node."""
        self.build("xy")
        with self.assertRaises(RuntimeError):
            self.bake()
        self.assertIn("Datacube Texture", self.node.message)
        self.assertNotIn(self.obj_name, bpy.data.objects)
        self.assertEqual(self.vdb_files(), [])

    def test_xyzt_static_refused(self):
        """A 4-D field with nothing animated asks for Animate along."""
        self.build("xyzt", animate_dim="NONE")
        with self.assertRaises(RuntimeError):
            self.bake()
        self.assertIn("Animate along", self.node.message)
        self.assertNotIn(self.obj_name, bpy.data.objects)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestDatacubeVolume)
test = unittest.TextTestRunner(verbosity=2).run(suite)

ret = not test.wasSuccessful()
sys.exit(ret)
