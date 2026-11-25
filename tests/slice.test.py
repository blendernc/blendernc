"""Slice a synthetic variable or datacube with the Datacube Slice node.

The dataset is ``(time, Z, Y, X)`` noise with a 2-D ``area`` coordinate.
The node keeps a range by index or by coordinate value; the tests read the
variable back through the slicing the node recorded and compare it with
``isel`` on the original dataset. A Subsample stride on the same dimension
must combine with the range, whichever node comes first. The node also
takes a datacube, and then the range reaches the coordinates too, so a grid
baked after the node is cropped like the variable. A coordinate linked as
the variable is sliced along itself.
"""

import os
import shutil
import sys
import tempfile
import unittest

import bpy
import numpy as np
import xarray as xr

from blendernc.core.slicing import merge_slicings
from blendernc.decorators import flush_pending_unlinks
from blendernc.node_utils import create_blenderncnodetree
from blendernc.utils import get_data_from_datastruct, get_dataset

NX, NY, NZ, NT = 6, 8, 4, 5
VARIABLE = "noise"
DATACUBE = "xarray datacube"
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
        import_node = self.import_node = tree.nodes.new("BlenderNCNodeImport")
        self.variable = tree.nodes.new("BlenderNCNodeVariable")
        import_node.datacube_file = self.path
        tree.links.new(import_node.outputs[DATACUBE], self.variable.inputs[DATACUBE])
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
            self.tree.links.new(source, node.inputs[0])
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

    # -- datacube input -------------------------------------------------------

    def datacube_chain(self, *bl_idnames):
        """Link nodes after the Import node through datacube sockets; return them.

        Each node is linked to the last one with a datacube output, so a
        Variable or Coords node is a branch.
        """
        source = self.import_node.outputs[DATACUBE]
        nodes = []
        for bl_idname in bl_idnames:
            node = self.tree.nodes.new(bl_idname)
            self.tree.links.new(source, node.inputs[0])
            if node.outputs.get(DATACUBE):
                source = node.outputs[DATACUBE]
            nodes.append(node)
        return nodes

    def test_output_follows_the_input(self):
        """A variable gives a Variable output, a datacube a datacube output.

        Linking a datacube in place of the variable replaces the output, and
        the links of the old output go with it; the bounds are kept.
        """
        empty = self.tree.nodes.new("BlenderNCNodeSlice")
        grey = tuple(empty.inputs[0].draw_color(bpy.context, empty))
        cut = self.slice_node("Y", first=2, last=5)
        self.assertEqual(cut.inputs[0].bl_idname, "bNCVariableOrDatacubeSocket")
        string_color = tuple(cut.inputs[0].draw_color(bpy.context, cut))
        self.assertEqual([s.bl_idname for s in cut.outputs], ["NodeSocketString"])
        self.assertEqual(cut.outputs["Variable"].default_value, VARIABLE)
        select = self.tree.nodes.new("BlenderNCNodeSelect")
        self.tree.links.new(cut.outputs["Variable"], select.inputs["Variable"])

        self.tree.links.new(self.import_node.outputs[DATACUBE], cut.inputs[0])
        self.assertEqual([s.name for s in cut.outputs], [DATACUBE])
        self.assertEqual(cut.outputs[0].bl_idname, "bNCdatacubeSocket")
        cube_color = tuple(cut.inputs[0].draw_color(bpy.context, cut))
        self.assertEqual(len({grey, string_color, cube_color}), 3)
        self.assertFalse(select.inputs["Variable"].is_linked)
        self.assertEqual((cut.first, cut.last), (2, 5))
        self.assert_sliced(cut, Y=slice(2, 6))

        self.tree.links.new(self.variable.outputs[VARIABLE], cut.inputs[0])
        self.assertEqual([s.name for s in cut.outputs], ["Variable"])

    def test_other_links_are_removed(self):
        """Only variable and datacube outputs may feed the input."""
        coords = self.coords_node()
        obj = self.bake_grid(coords.outputs["X"], coords.outputs["Y"], "LinkGrid")
        grid = next(n for n in self.tree.nodes if n.bl_idname == "BlenderNCNodeGrid")
        try:
            cut = self.tree.nodes.new("BlenderNCNodeSlice")
            with self.assertLogs(level="WARNING") as logs:
                self.tree.links.new(grid.outputs["Object"], cut.inputs[0])
            flush_pending_unlinks()  # timers do not run in background mode
            self.assertFalse(cut.inputs[0].is_linked)
            self.assertTrue(any("link removed" in line for line in logs.output))
        finally:
            self.remove_object(obj)

    def test_node_saved_with_a_variable_input(self):
        """A Slice node saved with a string input takes a datacube too."""
        cut = self.tree.nodes.new("BlenderNCNodeSlice")
        cut.inputs.clear()
        cut.inputs.new("NodeSocketString", "Variable")  # as saved before
        cut.outputs.new("NodeSocketString", "Variable")
        self.tree.links.new(self.variable.outputs[VARIABLE], cut.inputs["Variable"])
        cut.datacube_coords = "Y"
        cut.first, cut.last = 2, 5
        self.assert_sliced(cut, Y=slice(2, 6))

        self.tree.links.new(self.import_node.outputs[DATACUBE], cut.inputs["Variable"])
        flush_pending_unlinks()
        self.assertTrue(cut.inputs["Variable"].is_linked)
        self.assertEqual([s.name for s in cut.outputs], [DATACUBE])
        self.assert_sliced(cut, Y=slice(2, 6))

    # -- coordinate input -----------------------------------------------------

    def coords_node(self):
        """A Coords node linked to the Import node."""
        (coords,) = self.datacube_chain("BlenderNCNodeCoords")
        return coords

    def bake_grid(self, x_source, y_source, name):
        """Bake a Datacube Grid from two coordinate outputs; return the object."""
        grid = self.tree.nodes.new("BlenderNCNodeGrid")
        self.tree.links.new(x_source, grid.inputs["X"])
        self.tree.links.new(y_source, grid.inputs["Y"])
        grid.grid_obj_name = name
        bpy.ops.blendernc.create_grid_from_coords(
            node_name=grid.name, node_tree=self.tree.name
        )
        return bpy.data.objects[name]

    @staticmethod
    def remove_object(obj):
        """Delete a baked object and its mesh."""
        mesh = obj.data
        bpy.data.objects.remove(obj)
        bpy.data.meshes.remove(mesh)

    def test_coordinate_is_sliced_along_itself(self):
        """A linked 1-D coordinate picks itself, starting from its full range.

        Linking it again keeps the bounds; another coordinate resets them,
        and a 2-D one leaves the coordinate to the drop-down.
        """
        coords = self.coords_node()
        cut = self.tree.nodes.new("BlenderNCNodeSlice")
        self.tree.links.new(coords.outputs["Y"], cut.inputs[0])
        self.assertEqual(cut.datacube_coords, "Y")
        self.assertEqual((cut.first, cut.last), (0, NY - 1))
        self.assertEqual(cut.outputs["Variable"].default_value, "Y")

        cut.first, cut.last = 2, 5
        sliced = get_data_from_datastruct(cut.BNC_datastructs[0], "Y")
        np.testing.assert_allclose(sliced.values, Y_VALUES[2:6])
        self.tree.links.new(coords.outputs["Y"], cut.inputs[0])
        self.assertEqual((cut.first, cut.last), (2, 5))

        self.tree.links.new(coords.outputs["X"], cut.inputs[0])
        self.assertEqual(cut.datacube_coords, "X")
        self.assertEqual((cut.first, cut.last), (0, NX - 1))
        self.tree.links.new(coords.outputs["area"], cut.inputs[0])
        self.assertEqual(cut.datacube_coords, "X")

    def test_sliced_coordinate_crops_the_grid(self):
        """Slicing the X output of a Coords node crops the grid baked from it."""
        coords = self.coords_node()
        cut = self.tree.nodes.new("BlenderNCNodeSlice")
        self.tree.links.new(coords.outputs["X"], cut.inputs[0])
        cut.first, cut.last = 1, 3
        obj = self.bake_grid(cut.outputs["Variable"], coords.outputs["Y"], "CoordGrid")
        try:
            self.assertEqual(len(obj.data.vertices), 3 * NY)
        finally:
            self.remove_object(obj)

    def test_datacube_slice_reaches_variables_and_coordinates(self):
        """Every variable and coordinate after the node is sliced."""
        cut, variable, coords = self.datacube_chain(
            "BlenderNCNodeSlice", "BlenderNCNodeVariable", "BlenderNCNodeCoords"
        )
        cut.datacube_coords = "Y"
        cut.first, cut.last = 2, 5
        self.assertIn("positions 2 to 5", cut.summary)

        expected = self.dataset.isel(Y=slice(2, 6))
        self.assertEqual([s.name for s in variable.outputs], [VARIABLE])
        self.assertEqual(
            sorted(s.name for s in coords.outputs), sorted(expected.coords)
        )
        self.assert_sliced(variable, Y=slice(2, 6))
        for name in ("Y", "area"):
            data = get_data_from_datastruct(coords.BNC_datastructs[0], name)
            np.testing.assert_allclose(data.values, expected[name].values)

    def test_grid_after_datacube_slice_fits_the_texture(self):
        """The grid baked after the node is cropped like the variable on it.

        Widening the range rebakes the grid and rewrites the texture.
        """
        tree = self.tree
        cut, coords, variable = self.datacube_chain(
            "BlenderNCNodeSlice", "BlenderNCNodeCoords", "BlenderNCNodeVariable"
        )
        cut.datacube_coords = "X"
        cut.slice_by = "VALUE"
        cut.minimum, cut.maximum = 1.0, 3.0

        grid = tree.nodes.new("BlenderNCNodeGrid")
        tree.links.new(coords.outputs["X"], grid.inputs["X"])
        tree.links.new(coords.outputs["Y"], grid.inputs["Y"])
        grid.grid_obj_name = "SliceGrid"
        bpy.ops.blendernc.create_grid_from_coords(
            node_name=grid.name, node_tree=tree.name
        )
        obj = bpy.data.objects["SliceGrid"]
        try:
            source = variable.outputs[VARIABLE]
            for coord in ("time", "Z"):
                select = tree.nodes.new("BlenderNCNodeSelect")
                tree.links.new(source, select.inputs["Variable"])
                select.datacube_coords = coord
                source = select.outputs["Variable"]
            texture = tree.nodes.new("BlenderNCNodeTexture")
            tree.links.new(grid.outputs["Object"], texture.inputs["Object"])
            tree.links.new(source, texture.inputs["Variable"])

            for kept in (3, 4):
                with self.subTest(kept=kept):
                    cut.maximum = float(kept)
                    self.assertEqual(len(obj.data.vertices), kept * NY)
                    self.assertEqual(texture.message, "")
                    values = obj.data.attributes[VARIABLE].data
                    self.assertEqual(len(values), kept * NY)
        finally:
            mesh = obj.data
            bpy.data.objects.remove(obj)
            bpy.data.meshes.remove(mesh)

    def test_grid_keeps_a_range_from_any_input(self):
        """A range on the X input survives inputs taken upstream of the Slice.

        Y comes from a Coords node on the Import node and Z from a variable
        that never went through the Slice; the grid used to keep only the
        slicing of its last input, Z, and baked the whole X range.
        """
        tree = self.tree
        cut, sliced = self.datacube_chain("BlenderNCNodeSlice", "BlenderNCNodeCoords")
        (whole,) = self.datacube_chain("BlenderNCNodeCoords")
        cut.datacube_coords = "X"
        cut.first, cut.last = 1, 3
        source = self.variable.outputs[VARIABLE]
        for coord in ("time", "Z"):
            select = tree.nodes.new("BlenderNCNodeSelect")
            tree.links.new(source, select.inputs["Variable"])
            select.datacube_coords = coord
            source = select.outputs["Variable"]

        grid = tree.nodes.new("BlenderNCNodeGrid")
        tree.links.new(sliced.outputs["X"], grid.inputs["X"])
        tree.links.new(whole.outputs["Y"], grid.inputs["Y"])
        tree.links.new(source, grid.inputs["Z"])
        heights = get_data_from_datastruct(grid.BNC_datastructs[0], VARIABLE)
        self.assertEqual(dict(heights.sizes), {"Y": NY, "X": 3})

        grid.grid_obj_name = "RangeGrid"
        bpy.ops.blendernc.create_grid_from_coords(
            node_name=grid.name, node_tree=tree.name
        )
        obj = bpy.data.objects["RangeGrid"]
        try:
            self.assertEqual(len(obj.data.vertices), 3 * NY)
            cut.last = 4  # rebakes through the X input
            self.assertEqual(len(obj.data.vertices), 4 * NY)
        finally:
            mesh = obj.data
            bpy.data.objects.remove(obj)
            bpy.data.meshes.remove(mesh)

    def test_merge_slicings(self):
        """Records before a branch are kept once, then each branch's own."""
        stride = "*|Y|0::2,*|X|0::2,"
        on_x, on_y = "*|X|1:4:2,", "*|Y|2:6:2,"
        cases = [
            ([], ""),
            (["", ""], ""),
            (["*|X|1:4:,", ""], "*|X|1:4:,"),
            (["", "*|X|1:4:,"], "*|X|1:4:,"),
            ([stride, stride], stride),
            ([stride + on_x, stride], stride + on_x),
            ([stride, stride + on_x], stride + on_x),
            ([stride + on_x, stride, ""], stride + on_x),
            ([stride + on_x, stride + on_y], stride + on_x + on_y),
            (["*|X|1:4:,", "*|time|0,*|Z|0,"], "*|X|1:4:,*|time|0,*|Z|0,"),
        ]
        for slicings, expected in cases:
            with self.subTest(slicings=slicings):
                self.assertEqual(merge_slicings(slicings), expected)

    def test_datacube_range_and_resolution_combine_in_either_order(self):
        """Resolution then Slice, or Slice then Resolution, keep both."""
        for order in (
            ("BlenderNCNodeResolution", "BlenderNCNodeSlice"),
            ("BlenderNCNodeSlice", "BlenderNCNodeResolution"),
        ):
            with self.subTest(order=order):
                *chain, variable = self.datacube_chain(*order, "BlenderNCNodeVariable")
                nodes = dict(zip(order, chain))
                resolution = nodes["BlenderNCNodeResolution"]
                resolution.suggested_step = False
                resolution.step = 2
                cut = nodes["BlenderNCNodeSlice"]
                cut.datacube_coords = "Y"
                cut.first, cut.last = 2, 7
                self.assert_sliced(variable, Y=slice(2, 8, 2), X=slice(0, None, 2))
                for node in (*chain, variable):
                    self.tree.nodes.remove(node)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestDatacubeSlice)
test = unittest.TextTestRunner(verbosity=2).run(suite)

ret = not test.wasSuccessful()
sys.exit(ret)
