import os
import sys
import unittest

import bpy


class Test_import_mfdataset(unittest.TestCase):
    def test_import_mfdataset(self):
        bpy.ops.blendernc.import_mfdataset(
            node_name="Datacube Import",
            node_tree="BLENDERNC",
            directory=os.path.abspath("./dataset/"),
            files=({"name": "ssh_1995-01.nc"}, {"name": "ssh_1995-02.nc"}),
        )
        node_tree = bpy.data.node_groups.get("BLENDERNC")
        node = node_tree.nodes.get("Datacube Import")
        datastruct = node.BNC_datastructs[0]
        datastruct_exists = datastruct.datafile == os.path.abspath(
            "./dataset/ssh_1995-0*.nc"
        )
        self.assertTrue(datastruct_exists)

    # def test_non_existing_file(self):
    #     bpy.ops.blendernc.import_mfdataset(
    #         node_name="Datacube Import",
    #         node_tree="BLENDERNC",
    #         directory=os.path.abspath("./dataset/"),
    #         files=({"name": "non_existing_file.nc"},),
    #     )
    #     node_tree = bpy.data.node_groups.get("BLENDERNC")
    #     node = node_tree.nodes.get("Datacube Import")
    #     datastruct = node.BNC_datastructs[0]
    #     datastruct_exists = datastruct.datafile == os.path.abspath(
    #         "./dataset/non_existing_file.nc"
    #     )
    #     print(datastruct.datafile)
    #     self.assertFalse(datastruct_exists)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_import_mfdataset)
test = unittest.TextTestRunner().run(suite)

ret = not test.wasSuccessful()
sys.exit(ret)
