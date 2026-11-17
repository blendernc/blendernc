"""Slice a synthetic variable with the Datacube Slice node.

The dataset is ``(time, Z, Y, X)`` noise with a 2-D ``area`` coordinate.
The node keeps a range by index or by coordinate value; the tests read the
variable back through the slicing the node recorded and compare it with
``isel`` on the original dataset. A Subsample stride on the same dimension
must combine with the range, whichever node comes first.
"""

import os
import shutil
import sys
import tempfile
import unittest

import bpy
import numpy as np
import xarray as xr

from blendernc.node_utils import create_blenderncnodetree
from blendernc.utils import get_data_from_datastruct, get_dataset

NX, NY, NZ, NT = 6, 8, 4, 5
VARIABLE = "noise"
Y_VALUES = np.linspace(-80.0, 80.0, NY)


def make_dataset(path):
    """Write the ``(time, Z, Y, X)`` dataset and return it."""
    rng = np.random.default_rng(5)
    start = np.datetime64("2000-01-01")
    coords = {
        "time": start + np.arange(NT).astype("timedelta64[D]"),
        "Z": np.linspace(0.0, 300.0, NZ),
        "Y": Y_VALUES,
        "X": np.arange(float(NX)),
        "area": (("Y", "X"), rng.random((NY, NX))),
    }
    values = rng.standard_normal((NT, NZ, NY, NX))
    dataset = xr.Dataset({VARIABLE: (("time", "Z", "Y", "X"), values)}, coords=coords)
    dataset.to_netcdf(path)
    return dataset


class TestDatacubeSlice(unittest.TestCase):
    """Range selection by index and by value."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp(prefix="blendernc_slice_")
        cls.path = os.path.join(cls.tmpdir, "cube.nc")
        cls.dataset = make_dataset(cls.path)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def setUp(self):
        self.tree = create_blenderncnodetree(f"BNC_SLICE_{self._testMethodName}")
        tree = self.tree
        import_node = tree.nodes.new("BlenderNCNodeImport")
        self.variable = tree.nodes.new("BlenderNCNodeVariable")
        import_node.datacube_file = self.path
        datacube = "xarray datacube"
        tree.links.new(import_node.outputs[datacube], self.variable.inputs[datacube])
        self.assertIsNotNone(get_dataset(import_node.BNC_datastructs[0]))
        self.variable.datacube_vars = VARIABLE

    def tearDown(self):
        bpy.data.node_groups.remove(self.tree)

    # -- helpers --------------------------------------------------------------

    def chain(self, *bl_idnames):
        """Link nodes after the variable node, in order; return them."""
        source = self.variable.outputs[VARIABLE]
        nodes = []
        for bl_idname in bl_idnames:
            node = self.tree.nodes.new(bl_idname)
            self.tree.links.new(source, node.inputs["Variable"])
            source = node.outputs["Variable"]
            nodes.append(node)
        return nodes

    def slice_node(self, coord, **settings):
        """A Slice node on ``coord`` with ``settings`` applied in order."""
        (node,) = self.chain("BlenderNCNodeSlice")
        node.datacube_coords = coord
        for name, value in settings.items():
            setattr(node, name, value)
        return node

    def result(self, node):
        """The variable as the nodes after ``node`` would read it."""
        return get_data_from_datastruct(node.BNC_datastructs[0], VARIABLE)

    def assert_sliced(self, node, **isel):
        """``node``'s output equals the dataset after ``isel``."""
        expected = self.dataset[VARIABLE].isel(isel)
        np.testing.assert_allclose(self.result(node).values, expected.values)

    # -- by index -------------------------------------------------------------

    def test_new_coordinate_starts_with_full_range(self):
        """Picking a coordinate sets the bounds to its whole extent."""
        node = self.slice_node("Y")
        self.assertEqual((node.first, node.last), (0, NY - 1))
        self.assertAlmostEqual(node.minimum, -80.0, places=4)
        self.assertAlmostEqual(node.maximum, 80.0, places=4)
        self.assertEqual(self.result(node).sizes["Y"], NY)
        self.assertIn(f"positions 0 to {NY - 1}", node.summary)

    def test_index_range(self):
        """First and Last are both kept."""
        node = self.slice_node("Z", first=1, last=2)
        self.assert_sliced(node, Z=slice(1, 3))
        self.assertEqual(node.message, "")

    def test_index_bounds_in_either_order_and_clamped(self):
        """Swapped bounds are put in order; Last is clamped to the size."""
        node = self.slice_node("Y", first=5, last=2)
        self.assert_sliced(node, Y=slice(2, 6))
        node.last = 99
        node.first = 3
        self.assert_sliced(node, Y=slice(3, NY))

    def test_dates_by_index(self):
        """A time coordinate is sliced by index."""
        node = self.slice_node("time", first=1, last=3)
        self.assert_sliced(node, time=slice(1, 4))
        self.assertIn("2000-01-02", node.summary)

    # -- by value -------------------------------------------------------------

    def test_value_range(self):
        """Minimum and Maximum keep the values between them."""
        node = self.slice_node("Y", slice_by="VALUE", minimum=-30.0, maximum=30.0)
        inside = np.flatnonzero((Y_VALUES >= -30.0) & (Y_VALUES <= 30.0))
        self.assert_sliced(node, Y=slice(inside[0], inside[-1] + 1))

    def test_value_bounds_on_coordinate_values(self):
        """Bounds equal to coordinate values keep them despite float32 rounding."""
        node = self.slice_node("Y", slice_by="VALUE")
        node.minimum, node.maximum = Y_VALUES[2], Y_VALUES[5]
        self.assert_sliced(node, Y=slice(2, 6))

    def test_value_range_outside_data(self):
        """No value in range: nothing is sliced and the node says why."""
        node = self.slice_node("Y", slice_by="VALUE", minimum=100.0, maximum=200.0)
        self.assertIn("No Y value", node.message)
        self.assertEqual(self.result(node).sizes["Y"], NY)

    def test_dates_by_value_refused(self):
        """Dates cannot be typed as floats, so value mode asks for index mode."""
        node = self.slice_node("time", slice_by="VALUE")
        self.assertIn("Slice it by index", node.message)
        self.assertEqual(self.result(node).sizes["time"], NT)

    def test_2d_coordinate_refused(self):
        """A range only makes sense along a 1-D coordinate."""
        node = self.slice_node("area")
        self.assertIn("area is 2D", node.message)
        self.assertEqual(self.result(node).sizes["Y"], NY)

    def test_picking_a_coordinate_rebakes_downstream_once(self):
        """Resetting the bounds of a new coordinate slices once, not per bound."""
        cut = self.slice_node("Z")
        volume = self.tree.nodes.new("BlenderNCNodeVolume")
        volume.vdb_dir = os.path.join(self.tmpdir, "vdb")
        volume.volume_obj_name = "SliceVolume"
        self.tree.links.new(cut.outputs["Variable"], volume.inputs["Variable"])
        bpy.ops.blendernc.create_volume(node_name=volume.name, node_tree=self.tree.name)
        obj = bpy.data.objects["SliceVolume"]
        try:
            token = volume.bake_token
            cut.datacube_coords = "Y"
            self.assertEqual(volume.bake_token, token + 1)
        finally:
            data = obj.data
            bpy.data.objects.remove(obj)
            bpy.data.volumes.remove(data)

    # -- with a stride --------------------------------------------------------

    def test_range_and_stride_combine_in_either_order(self):
        """Subsample then Slice, or Slice then Subsample, keep both."""
        for order in (
            ("BlenderNCNodeSubsample", "BlenderNCNodeSlice"),
            ("BlenderNCNodeSlice", "BlenderNCNodeSubsample"),
        ):
            with self.subTest(order=order):
                nodes = dict(zip(order, self.chain(*order)))
                subsample = nodes["BlenderNCNodeSubsample"]
                subsample.datacube_coords = "Y"
                subsample.step = 2
                cut = nodes["BlenderNCNodeSlice"]
                cut.datacube_coords = "Y"
                cut.first, cut.last = 2, 7
                self.assert_sliced(nodes[order[-1]], Y=slice(2, 8, 2))
                for node in nodes.values():
                    self.tree.nodes.remove(node)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestDatacubeSlice)
test = unittest.TextTestRunner(verbosity=2).run(suite)

ret = not test.wasSuccessful()
sys.exit(ret)
