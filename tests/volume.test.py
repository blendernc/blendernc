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
rectilinear, a depth axis marked ``positive = "down"`` and uneven levels.

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

from blendernc.handlers import bNC_update_volumes
from blendernc.node_utils import create_blenderncnodetree
from blendernc.utils import RANGE_PROPERTIES, get_dataset
from blendernc.volume_utils import (
    UNSAVED_WARNING,
    get_animate_dims,
    nearest_positions,
    vdb_directory,
)

NX, NY, NZ, NT = 12, 8, 4, 5
VARIABLE = "noise"
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
    path, x=X_VALUES, y=Y_VALUES, z=Z_VALUES, z_attrs=None, coords_2d=None
):
    """Write an ``(X, Y, Z)`` noise dataset with the given axes; return it.

    ``coords_2d`` maps extra coordinate names to ``(Y, X)`` arrays, such as
    a curvilinear longitude and latitude.
    """
    rng = np.random.default_rng(3)
    coords = {"X": ("X", x), "Y": ("Y", y), "Z": ("Z", z, z_attrs or {})}
    for name, values in (coords_2d or {}).items():
        coords[name] = (("Y", "X"), values)
    values = rng.standard_normal((len(z), len(y), len(x)))
    dataset = xr.Dataset({VARIABLE: (("Z", "Y", "X"), values)}, coords=coords)
    dataset.to_netcdf(path)
    return dataset


def rotated_grid():
    """Longitude and latitude of a grid rotated by ``ANGLE``, unit spacing."""
    j, i = np.meshgrid(np.arange(NY), np.arange(NX), indexing="ij")
    lon = 10.0 + i * np.cos(ANGLE) - j * np.sin(ANGLE)
    lat = 20.0 + i * np.sin(ANGLE) + j * np.cos(ANGLE)
    return lon, lat


def read_grid(path, shape):
    """Read the variable's grid from a VDB file into an array of ``shape``."""
    grid = openvdb.read(path, VARIABLE)
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
        ):
            path = os.path.join(cls.tmpdir, f"{key}.nc")
            cls.datasets[key] = make_xyz_variant(path, **kwargs)
            cls.files[key] = path

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
        variable = tree.nodes.new("BlenderNCNodeVariable")
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

    def expected(self, key, vertical, **isel):
        """The variable as an ``(X, Y, vertical)`` array, after ``isel``."""
        data = self.datasets[key][VARIABLE].isel(isel)
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
        density = nodes["Principled Volume"].inputs["Density"]
        self.assertTrue(density.is_linked)
        self.assertEqual(density.links[0].from_node.bl_idname, "ShaderNodeMapRange")
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

    def test_select_change_rebakes(self):
        """Selecting another level rebakes the volume with new file names."""
        self.build("xyzt", select_z=0)
        self.bake()
        token = self.node.bake_token
        self.select.index = 2  # (time, Y, X) -> space-time cube of level 2
        self.assertGreater(self.node.bake_token, token)
        files = self.vdb_files()
        self.assertEqual(len(files), 1)
        np.testing.assert_allclose(
            read_grid(files[0], (NX, NY, NT)),
            self.expected("xyzt", "time", Z=2),
            rtol=1e-6,
        )

    # -- placement ------------------------------------------------------------

    def read_single(self, key):
        """Bake dataset ``key`` and read its only VDB file back."""
        self.build(key)
        obj = self.bake()
        files = self.vdb_files()
        self.assertEqual(len(files), 1)
        return obj, read_grid(files[0], (NX, NY, NZ))

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

        background = float(dataset[VARIABLE].min())
        # The bounding box corner at (min lon, min lat) lies outside the data.
        np.testing.assert_allclose(grid[0, 0], background, rtol=1e-6)
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

    def test_uneven_levels_keep_one_voxel_per_level(self):
        """Uneven Z levels stay one voxel each, with a note on the node."""
        obj, grid = self.read_single("uneven_z")
        np.testing.assert_allclose(grid, self.expected("uneven_z", "Z"), rtol=1e-6)
        self.assertAlmostEqual(obj.scale.z, 1.0)
        self.assertIn("Z is unevenly spaced", self.node.note)

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
