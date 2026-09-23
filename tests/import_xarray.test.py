import os
import sys
import unittest

import bpy

from blendernc.utils import create_datastruct, load_dataset


def update_datacube_file(file):
    bpy.data.scenes["Scene"].BlenderNC_UI_Properties.datacube_file = file


class Test_import(unittest.TestCase):
    def test_import_datacube(self):
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

    def test_remove_all_nodes(self):
        node_tree = bpy.data.node_groups.get("BLENDERNC")
        for node in list(node_tree.nodes):
            node_tree.nodes.remove(node)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_import)
test = unittest.TextTestRunner().run(suite)

ret = not test.wasSuccessful()
sys.exit(ret)
