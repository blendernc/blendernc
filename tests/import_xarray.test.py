import os
import sys
import unittest

import bpy

from blendernc.node_utils import create_blenderncnodetree
from blendernc.utils import store_dataset


def update_datacube_file(file):
    """Set the datacube path on the scene UI properties, triggering a load."""
    bpy.data.scenes["Scene"].BlenderNC_UI_Properties.datacube_file = file


class Test_import(unittest.TestCase):
    """Loading datacubes through the 3D view panel property."""

    def test_import_datacube(self):
        """A single file path is stored and its dataset cached."""
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        update_datacube_file(file)
        node_tree = bpy.data.node_groups.get("BLENDERNC")
        node = node_tree.nodes.get("Datacube Import")
        datastruct = node.BNC_datastructs[0]
        datastruct_exists = datastruct.datafile == file
        datastruct_dict_exists = datastruct.dict[datastruct.filename] is not None
        self.assertTrue(datastruct_dict_exists)
        self.assertTrue(datastruct_exists)

    def test_import_mfdataset_pattern(self):
        """A glob pattern is stored and opened as a multi-file dataset."""
        file = os.path.abspath("./dataset/ssh_*.nc")
        bpy.data.scenes["Scene"].BlenderNC_UI_Properties.datacube_file = file
        node_tree = bpy.data.node_groups.get("BLENDERNC")
        node = node_tree.nodes.get("Datacube Import")
        datastruct = node.BNC_datastructs[0]
        datastruct_exists = datastruct.datafile == file
        datastruct_dict_exists = datastruct.dict[datastruct.filename] is not None
        self.assertTrue(datastruct_dict_exists)
        self.assertTrue(datastruct_exists)

    def test_file_missing(self):
        """A missing file is logged, leaves no dataset and disconnects the tree."""
        file = os.path.abspath("./dataset/abc.nc")

        scratch = create_blenderncnodetree("BNC_SCRATCH")
        node = scratch.nodes.new("BlenderNCNodeImport")
        with self.assertLogs("blendernc.messages", level="ERROR"):
            self.assertFalse(store_dataset(node.BNC_datastructs[0], file))
        self.assertEqual(node.BNC_datastructs[0].filename, "")
        bpy.data.node_groups.remove(scratch)

        with self.assertLogs("blendernc.messages", level="WARNING"):
            update_datacube_file(file)
        import_node = bpy.data.node_groups["BLENDERNC"].nodes["Datacube Import"]
        self.assertFalse(import_node.outputs[0].is_linked)

    def test_operator_missing_file_reports_and_cancels(self):
        """The import operator reports the problem and logs it.

        In the UI the report lands in the status bar. When an operator is
        called from Python, Blender re-raises an ``ERROR`` report as a
        ``RuntimeError`` carrying the same message.
        """
        with self.assertLogs("blendernc", level="ERROR") as logs:
            with self.assertRaisesRegex(RuntimeError, "Could not open .*abc.nc"):
                bpy.ops.blendernc.import_mfdataset(
                    node_name="Datacube Import",
                    node_tree="BLENDERNC",
                    directory=os.path.abspath("./dataset/"),
                    files=({"name": "abc.nc"},),
                )
        self.assertTrue(any("Could not open" in line for line in logs.output))

    def test_remove_all_nodes(self):
        """Clean up by removing every node from the ``BLENDERNC`` tree."""
        node_tree = bpy.data.node_groups.get("BLENDERNC")
        for node in list(node_tree.nodes):
            node_tree.nodes.remove(node)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_import)
test = unittest.TextTestRunner().run(suite)

ret = not test.wasSuccessful()
sys.exit(ret)
