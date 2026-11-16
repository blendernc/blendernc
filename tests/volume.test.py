"""Bake Datacube Volume nodes from synthetic xarray datasets.

Four datasets are generated on the fly with a random-noise variable:

* ``(X, Y)``: refused, a volume needs three dimensions.
* ``(X, Y, Z)``: one static volume, Z vertical.
* ``(X, Y, time)``: a static space-time cube, time vertical; or, with
  "Animate along" set to time, a one-voxel-thick slab per frame.
* ``(X, Y, Z, time)``: a volume animated along time, either as a VDB
  sequence ("Bake all frames") or one file per shown frame ("Current frame").

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

NX, NY, NZ, NT = 12, 8, 4, 5
VARIABLE = "noise"
X_VALUES = np.linspace(0.0, 360.0, NX, endpoint=False)
Y_VALUES = np.linspace(-80.0, 80.0, NY)


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
        np.testing.assert_allclose(obj.scale, (30.0, 160.0 / 7, 1.0), rtol=1e-5)
        data = self.datasets["xyz"][VARIABLE]
        self.assertAlmostEqual(obj[RANGE_PROPERTIES[0]], float(data.min()), places=5)
        self.assertAlmostEqual(obj[RANGE_PROPERTIES[1]], float(data.max()), places=5)
        self.assertEqual(self.node.message, "")
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
        """Changing the vertical scale only changes the object's z scale."""
        self.build("xyz")
        obj = self.bake()
        token = self.node.bake_token
        self.node.vertical_scale = 25.0
        self.assertAlmostEqual(obj.scale.z, 25.0)
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
