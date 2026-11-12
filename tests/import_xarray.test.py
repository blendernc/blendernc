import os
import sys
import unittest

import bpy

from blendernc.utils import create_datastruct, load_dataset


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
        """A missing file raises on direct load and is tolerated by the UI path."""
        file = os.path.abspath("./dataset/abc.nc")
        with self.assertRaises(FileNotFoundError):
            load_dataset(file)
        fake_self = type(
            "obj",
            (object,),
            {
                "node_tree": "BLENDERNC",
                "node_name": "Datacube Import",
                "bl_idname": "BlenderNC_UI_Properties",
            },
        )
        fake_context = type("obj", (object,), {"scene": bpy.data.scenes["Scene"]})
        create_datastruct(fake_self, fake_context)
        # TODO: create_datastruct only tests for it to not
        # raise an exception. Further validation should be added.
        # For example test that no datastruct is created when the
        # file is missing, and all nodes are disconnected.

    def test_remove_all_nodes(self):
        """Clean up by removing every node from the ``BLENDERNC`` tree."""
        node_tree = bpy.data.node_groups.get("BLENDERNC")
        for node in list(node_tree.nodes):
            node_tree.nodes.remove(node)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_import)
test = unittest.TextTestRunner().run(suite)

ret = not test.wasSuccessful()
sys.exit(ret)
