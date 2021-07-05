import os
import unittest

import bpy

from blendernc.get_utils import get_blendernc_nodetrees


class Test_operators(unittest.TestCase):
    def test_ui_no_file(self):
        bpy.ops.blendernc.var(file_path="")

    def test_ui_file(self):
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        bpy.ops.blendernc.var(file_path=file)
        # self.assertRaises(ExpectedException, test_no_selected_file, nodes)

    def test_ui_remove_cache_no_nodetree(self):
        # No nodetree:
        bpy.ops.blendernc.purge_all()

    def test_ui_remove_cache_nodetree(self):
        # Node tree exists,
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        bpy.ops.blendernc.var(file_path=file)
        bpy.ops.blendernc.purge_all()

    def test_ui_remove_cache_with_cache(self):
        # Node tree exists,
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        bpy.ops.blendernc.var(file_path=file)
        blendernc_nodes = get_blendernc_nodetrees()
        inp = blendernc_nodes[0].nodes.get("netCDF input")
        inp.blendernc_netcdf_vars = "adt"
        bpy.ops.blendernc.ncload_sui()
        bpy.ops.blendernc.purge_all()

    def test_ui_remove_cache_with_cache_no_image(self):
        # Node tree exists,
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        bpy.ops.blendernc.var(file_path=file)
        blendernc_nodes = get_blendernc_nodetrees()
        inp = blendernc_nodes[0].nodes.get("netCDF input")
        inp.blendernc_netcdf_vars = "adt"
        bpy.ops.blendernc.ncload_sui()
        nodetree_name = blendernc_nodes[0].bl_idname
        cache_nodetree = bpy.context.scene.nc_cache[nodetree_name]
        [cache_nodetree.pop(key) for key in list(cache_nodetree.keys())]
        bpy.ops.blendernc.purge_all()


suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_operators)
unittest.TextTestRunner().run(suite)
