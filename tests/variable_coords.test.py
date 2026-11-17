"""Outputs of the Datacube Coords and Datacube Variable nodes.

Three synthetic datasets: ``first`` and ``second`` share the coordinates X
and Y and the variable ``b``; ``many`` has more variables than
``MAX_VARIABLE_OUTPUTS``. Linking another dataset replaces a node's outputs,
keeping the links of the names both datasets share. The variable node has
one output per variable, or a drop-down and a single ``"Variable"`` output
for ``many``, which the 3D view panel links as well.
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
from blendernc.utils import MAX_VARIABLE_OUTPUTS, get_dataset

NX, NY = 5, 4
DATACUBE = "xarray datacube"
MANY = [f"v{index:02d}" for index in range(MAX_VARIABLE_OUTPUTS + 2)]


def write_datasets(directory):
    """Write the three datasets; return their paths by name."""
    rng = np.random.default_rng(2)
    horizontal = {"X": np.arange(float(NX)), "Y": np.arange(float(NY))}

    def field(*dims):
        sizes = {"time": 3, "depth": 2, "Y": NY, "X": NX}
        return dims, rng.standard_normal([sizes[dim] for dim in dims])

    datasets = {
        "first": xr.Dataset(
            {name: field("time", "Y", "X") for name in ("a", "b")},
            coords={
                **horizontal,
                "time": np.arange(3.0),
                "area": (("Y", "X"), rng.random((NY, NX))),
            },
        ),
        "second": xr.Dataset(
            {name: field("depth", "Y", "X") for name in ("b", "c")},
            coords={**horizontal, "depth": [5.0, 15.0]},
        ),
        "many": xr.Dataset({name: field("Y", "X") for name in MANY}, coords=horizontal),
    }
    paths = {}
    for name, dataset in datasets.items():
        paths[name] = os.path.join(directory, f"{name}.nc")
        dataset.to_netcdf(paths[name])
    return paths


class TestOutputs(unittest.TestCase):
    """Outputs follow the linked dataset."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp(prefix="blendernc_outputs_")
        cls.paths = write_datasets(cls.tmpdir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def setUp(self):
        self.tree = create_blenderncnodetree(f"BNC_OUT_{self._testMethodName}")

    def tearDown(self):
        bpy.data.node_groups.remove(self.tree)

    # -- helpers --------------------------------------------------------------

    def load(self, key):
        """A new Import node with dataset ``key`` loaded."""
        node = self.tree.nodes.new("BlenderNCNodeImport")
        node.datacube_file = self.paths[key]
        self.assertIsNotNone(get_dataset(node.BNC_datastructs[0]))
        return node

    def feed(self, import_node, node):
        """Link ``import_node``'s dataset into ``node``."""
        self.tree.links.new(import_node.outputs[DATACUBE], node.inputs[DATACUBE])

    def names(self, node):
        """Names of ``node``'s outputs, in order."""
        return [socket.name for socket in node.outputs]

    def coordinates(self, node):
        """Coordinate names of the dataset ``node`` reads, in dataset order."""
        dataset = get_dataset(node.BNC_datastructs[0])
        return [str(name) for name in dataset.coords]

    def debug(self, socket):
        """A Debug node reading ``socket``; return its input."""
        node = self.tree.nodes.new("BlenderNCNodeDebugNode")
        self.tree.links.new(socket, node.inputs[0])
        return node.inputs[0]

    # -- coordinates ----------------------------------------------------------

    def test_coords_replaced_by_a_new_dataset(self):
        """Another dataset replaces the coordinates; shared ones keep links."""
        coords = self.tree.nodes.new("BlenderNCNodeCoords")
        self.feed(self.load("first"), coords)
        self.assertEqual(self.names(coords), self.coordinates(coords))
        self.assertIn("time", self.names(coords))
        reader = self.debug(coords.outputs["X"])

        self.feed(self.load("second"), coords)
        self.assertEqual(self.names(coords), self.coordinates(coords))
        self.assertNotIn("time", self.names(coords))
        self.assertNotIn("area", self.names(coords))
        self.assertIn("depth", self.names(coords))
        self.assertTrue(reader.is_linked)
        self.assertEqual(reader.links[0].from_socket.name, "X")

    def test_coords_follow_a_new_file_on_the_same_import(self):
        """Pointing the Import node at another file replaces the coordinates."""
        coords = self.tree.nodes.new("BlenderNCNodeCoords")
        import_node = self.load("first")
        self.feed(import_node, coords)
        import_node.datacube_file = self.paths["second"]
        self.assertEqual(self.names(coords), self.coordinates(coords))
        self.assertIn("depth", self.names(coords))
        self.assertNotIn("time", self.names(coords))

    # -- variables ------------------------------------------------------------

    def test_one_output_per_variable(self):
        """A few variables: one output each, named after it, no drop-down."""
        variable = self.tree.nodes.new("BlenderNCNodeVariable")
        self.feed(self.load("first"), variable)
        self.assertFalse(variable.drop_down)
        self.assertEqual(self.names(variable), ["a", "b"])
        self.assertEqual([s.default_value for s in variable.outputs], ["a", "b"])
        self.assertEqual(variable.pick("b"), variable.outputs["b"])
        self.assertIsNone(variable.pick("nope"))

    def test_variables_replaced_by_a_new_dataset(self):
        """Another dataset replaces the variables; a shared one keeps its link."""
        variable = self.tree.nodes.new("BlenderNCNodeVariable")
        self.feed(self.load("first"), variable)
        reader = self.debug(variable.outputs["b"])
        self.feed(self.load("second"), variable)
        self.assertEqual(self.names(variable), ["b", "c"])
        self.assertTrue(reader.is_linked)
        self.assertEqual(reader.links[0].from_socket.name, "b")

    def test_many_variables_use_a_drop_down(self):
        """Too many variables: one output, kept when another is picked."""
        variable = self.tree.nodes.new("BlenderNCNodeVariable")
        self.feed(self.load("many"), variable)
        self.assertTrue(variable.drop_down)
        self.assertEqual(self.names(variable), [])

        output = variable.pick("v03")
        self.assertEqual(self.names(variable), ["Variable"])
        self.assertEqual(output.default_value, "v03")
        select = self.tree.nodes.new("BlenderNCNodeSelect")
        self.tree.links.new(output, select.inputs["Variable"])

        self.assertEqual(variable.pick("v07"), variable.outputs["Variable"])
        self.assertEqual(self.names(variable), ["Variable"])
        self.assertTrue(select.inputs["Variable"].is_linked)
        self.assertEqual(select.outputs["Variable"].default_value, "v07")
        self.assertIsNone(variable.pick("nope"))

    def test_from_many_variables_back_to_a_few(self):
        """Linking a smaller dataset brings back one output per variable."""
        variable = self.tree.nodes.new("BlenderNCNodeVariable")
        self.feed(self.load("many"), variable)
        variable.pick("v01")
        self.feed(self.load("first"), variable)
        self.assertFalse(variable.drop_down)
        self.assertEqual(self.names(variable), ["a", "b"])


class TestPanelDropDown(unittest.TestCase):
    """The panel links the single output of a variable node with a drop-down."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp(prefix="blendernc_panel_many_")
        cls.paths = write_datasets(cls.tmpdir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_panel_variable_goes_through_the_drop_down(self):
        """Picking in the panel selects the variable on the node's drop-down."""
        props = bpy.context.scene.BlenderNC_UI_Properties
        props.datacube_file = self.paths["many"]
        tree = bpy.data.node_groups["BLENDERNC"]
        props.X = "X"
        props.Y = "Y"
        variable = tree.nodes["Datacube Variable"]
        texture = tree.nodes["Datacube Texture"]
        self.assertTrue(variable.drop_down)
        for name in ("v02", "v05"):
            with self.subTest(variable=name):
                props.variable = name
                mesh = bpy.data.objects["Grid"].data
                link = texture.inputs["Variable"].links[0]
                self.assertEqual(link.from_socket.name, "Variable")
                self.assertEqual(variable.datacube_vars, name)
                self.assertEqual(texture.written, name)
                self.assertIn(name, mesh.attributes)


loader = unittest.defaultTestLoader
suite = unittest.TestSuite(
    [
        loader.loadTestsFromTestCase(TestOutputs),
        loader.loadTestsFromTestCase(TestPanelDropDown),
    ]
)
test = unittest.TextTestRunner(verbosity=2).run(suite)

ret = not test.wasSuccessful()
sys.exit(ret)
