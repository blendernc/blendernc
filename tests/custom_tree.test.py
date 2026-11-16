"""Node trees with any name, and a Debug node that takes any link.

A synthetic dataset is written on the fly. The tree is deliberately not
called ``BLENDERNC`` (the 3D view panel's tree): users build their own trees
for complex animations, and the Datacube Import file browser must load into
the node it was clicked on.
"""

import shutil
import sys
import tempfile
import unittest

import bpy
import numpy as np
import xarray as xr

from blendernc.decorators import flush_pending_unlinks
from blendernc.node_utils import UI_NODE_TREE, create_blenderncnodetree
from blendernc.nodes import _describe_value
from blendernc.utils import get_dataset

FILENAME = "synthetic.nc"
VARIABLE = "noise"


def write_dataset(path):
    """Write a small (Y, X) noise field to ``path``."""
    rng = np.random.default_rng(0)
    xr.Dataset(
        {VARIABLE: (("Y", "X"), rng.standard_normal((4, 6)))},
        coords={"X": np.arange(6.0), "Y": np.arange(4.0)},
    ).to_netcdf(path)


def remove_tree(name):
    """Remove the node group called ``name`` if it exists."""
    tree = bpy.data.node_groups.get(name)
    if tree is not None:
        bpy.data.node_groups.remove(tree)


class TestCustomTree(unittest.TestCase):
    """Import into, and debug, a tree that is not the panel's."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.path = f"{cls.tmpdir}/{FILENAME}"
        write_dataset(cls.path)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def setUp(self):
        remove_tree(UI_NODE_TREE)
        self.tree = create_blenderncnodetree("My Animation")

    def tearDown(self):
        remove_tree(self.tree.name)
        remove_tree(UI_NODE_TREE)

    def import_file(self, **kwargs):
        """Run the import operator on the synthetic file."""
        bpy.ops.blendernc.import_mfdataset(
            directory=self.tmpdir, files=({"name": FILENAME},), **kwargs
        )

    def loaded_import_node(self):
        """Return an import node of the custom tree with the file loaded."""
        node = self.tree.nodes.new("BlenderNCNodeImport")
        node.datacube_file = self.path
        return node

    # -- Datacube Import --------------------------------------------------

    def test_file_browser_loads_into_its_own_tree(self):
        """The node the button belongs to gets the file; no panel tree."""
        node = self.tree.nodes.new("BlenderNCNodeImport")
        self.import_file(node_name=node.name, node_tree=self.tree.name)
        self.assertEqual(node.datacube_file, self.path)
        self.assertIsNotNone(get_dataset(node.BNC_datastructs[0]))
        self.assertNotIn(UI_NODE_TREE, bpy.data.node_groups)

    def test_second_import_node_in_same_tree(self):
        """Each import node of a tree loads independently."""
        first = self.tree.nodes.new("BlenderNCNodeImport")
        second = self.tree.nodes.new("BlenderNCNodeImport")
        self.import_file(node_name=second.name, node_tree=self.tree.name)
        self.assertEqual(second.datacube_file, self.path)
        self.assertEqual(first.datacube_file, "")

    def test_panel_call_still_uses_panel_tree(self):
        """Without a tree, as from the 3D view, the panel tree is used.

        Only UI buttons reuse remembered operator values (``bpy.ops`` calls
        do not), so the ``SKIP_SAVE`` on ``node_tree`` cannot be checked here.
        """
        node = self.tree.nodes.new("BlenderNCNodeImport")
        self.import_file(node_name=node.name, node_tree=self.tree.name)
        self.import_file()
        panel_node = bpy.data.node_groups[UI_NODE_TREE].nodes["Datacube Import"]
        self.assertEqual(panel_node.datacube_file, self.path)

    def test_missing_node_reports_and_cancels(self):
        """A node that does not exist is reported, not a traceback."""
        with self.assertLogs("blendernc", level="ERROR") as logs:
            with self.assertRaisesRegex(RuntimeError, "not found in 'My Animation'"):
                self.import_file(node_name="Nope", node_tree=self.tree.name)
        self.assertTrue(any("not found" in line for line in logs.output))
        self.assertNotIn(UI_NODE_TREE, bpy.data.node_groups)

    # -- Debug node -------------------------------------------------------

    def link_debug(self, output, debug=None):
        """Link ``output`` to a (new) Debug node and run the pending unlinks."""
        debug = debug or self.tree.nodes.new("BlenderNCNodeDebugNode")
        self.tree.links.new(output, debug.inputs[0])
        flush_pending_unlinks()
        return debug

    def test_debug_accepts_datacube_link(self):
        """A datacube output stays linked and its data item is copied."""
        node = self.loaded_import_node()
        debug = self.link_debug(node.outputs["xarray datacube"])
        self.assertTrue(debug.inputs[0].is_linked)
        self.assertEqual(debug.BNC_datastructs[0].datafile, self.path)

    def test_debug_accepts_string_link(self):
        """A variable name output stays linked and keeps the data item."""
        node = self.loaded_import_node()
        variable = self.tree.nodes.new("BlenderNCNodeVariable")
        self.tree.links.new(node.outputs[0], variable.inputs[0])
        variable.datacube_vars = VARIABLE
        debug = self.link_debug(variable.outputs[VARIABLE])
        self.assertTrue(debug.inputs[0].is_linked)
        self.assertEqual(debug.BNC_datastructs[0].datafile, self.path)

    def test_debug_accepts_object_link(self):
        """An object output stays linked and shows the object's name."""
        obj = bpy.data.objects.new("Debug Grid", bpy.data.meshes.new("Debug Grid"))
        node = self.loaded_import_node()
        coords = self.tree.nodes.new("BlenderNCNodeCoords")
        grid = self.tree.nodes.new("BlenderNCNodeGrid")
        grid.grid_obj_name = obj.name  # the grid exposes it once linked
        self.tree.links.new(node.outputs[0], coords.inputs[0])
        self.tree.links.new(coords.outputs["X"], grid.inputs["X"])
        self.tree.links.new(coords.outputs["Y"], grid.inputs["Y"])

        debug = self.link_debug(grid.outputs["Object"])
        self.assertTrue(debug.inputs[0].is_linked)
        self.assertEqual(
            _describe_value(debug.inputs[0].links[0].from_socket), obj.name
        )
        bpy.data.objects.remove(obj)

    def test_old_debug_socket_accepts_any_link(self):
        """A Debug node saved with the datacube input takes a string too."""
        node = self.loaded_import_node()
        variable = self.tree.nodes.new("BlenderNCNodeVariable")
        self.tree.links.new(node.outputs[0], variable.inputs[0])
        variable.datacube_vars = VARIABLE
        debug = self.tree.nodes.new("BlenderNCNodeDebugNode")
        debug.inputs.clear()
        debug.inputs.new("bNCdatacubeSocket", "xarray datacube")
        self.link_debug(variable.outputs[VARIABLE], debug)
        self.assertTrue(debug.inputs[0].is_linked)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestCustomTree)
test = unittest.TextTestRunner(verbosity=2).run(suite)

ret = not test.wasSuccessful()
sys.exit(ret)
