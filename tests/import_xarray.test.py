import os
import sys
import unittest

import bpy

def update_datacube_file(file):
    bpy.data.scenes["Scene"].datacube_file = file

class Test_import(unittest.TestCase):
    def test_import_datacubes(self):
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        update_datacube_file(file)
        node_tree=bpy.data.node_groups.get("BLENDERNC")
        node = node_tree.nodes.get("Datacube Import")
        datastruct=node.BNC_datastructs[0]
        datastruct_exists = datastruct.datafile == file
        datastruct_dict_exists = datastruct.dict[datastruct.filename] is not None
        self.assertTrue(datastruct_dict_exists)
        self.assertTrue(datastruct_exists)

    def test_import_import_mfdataset(self):
        bpy.ops.blendernc.import_mfdataset(node_name="Datacube Import", node_tree="BLENDERNC", directory=os.path.abspath("./dataset/"), files=({'name': "ssh_1995-01.nc"}, {'name': "ssh_1995-02.nc"}))
        node_tree=bpy.data.node_groups.get("BLENDERNC")
        node = node_tree.nodes.get("Datacube Import")
        datastruct=node.BNC_datastructs[0]
        datastruct_exists = datastruct.datafile == os.path.abspath("./dataset/ssh_1995-0*.nc")
        self.assertTrue(datastruct_exists)

    def test_import_datacubes_multiple_files(self):
        file = os.path.abspath("./dataset/ssh_*.nc")
        bpy.data.scenes["Scene"].datacube_file = file
        node_tree=bpy.data.node_groups.get("BLENDERNC")
        node = node_tree.nodes.get("Datacube Import")
        datastruct=node.BNC_datastructs[0]
        datastruct_exists = datastruct.datafile == file
        datastruct_dict_exists = datastruct.dict[datastruct.filename] is not None
        self.assertTrue(datastruct_dict_exists)
        self.assertTrue(datastruct_exists)
        
    def test_file_missing(self):
        file = os.path.abspath("./dataset/abc.nc")
        with self.assertRaises(NameError):
            update_datacube_file(file)
            node_tree=bpy.data.node_groups.get("BLENDERNC")
            node = node_tree.nodes.get("Datacube Import")
            node.update()

suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_import)
test = unittest.TextTestRunner().run(suite)

ret = not test.wasSuccessful()
sys.exit(ret)
