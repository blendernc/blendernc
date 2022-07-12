import os
import sys
import unittest

import bpy

from blendernc.get_utils import get_blendernc_nodetrees
from blendernc.UI_operators import findCommonName


def change_file(file):
    bpy.ops.blendernc.var(file_path=file)


class Test_operators(unittest.TestCase):
    def test_compute_range(self):
        # Node tree exists,
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        change_file(file)
        blendernc_nodes = get_blendernc_nodetrees()
        node_tree = blendernc_nodes[0]
        inp = node_tree.nodes.get("datacube Input")
        inp.blendernc_datacube_vars = "adt"
        ran = node_tree.nodes.new("datacubeRange")
        node_tree.links.new(ran.inputs[0], inp.outputs[0])
        # TODO Force compute range here!
        node_tree_name = node_tree.bl_idname
        bpy.ops.blendernc.compute_range(
            node_group=node_tree_name, node="datacube Range"
        )
        # Delete node tree
        node_groups = bpy.data.node_groups
        node_groups.remove(node_groups["BlenderNC"])

    def test_ui_file(self):
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        change_file(file)

    def test_ui_no_existing_file(self):
        file = os.path.abspath("./dataset/abc.nc")
        with self.assertRaises(RuntimeError):
            change_file(file)

    def test_ui_no_file(self):
        bpy.ops.blendernc.var(file_path="")

    def test_ui_remove_cache_no_nodetree(self):
        # No nodetree:
        bpy.ops.blendernc.purge_all()

    def test_ui_remove_cache_nodetree(self):
        # Node tree exists,
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        change_file(file)
        bpy.ops.blendernc.purge_all()

    def test_ui_remove_cache_with_cache(self):
        # Node tree exists,
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        change_file(file)
        blendernc_nodes = get_blendernc_nodetrees()
        inp = blendernc_nodes[0].nodes.get("datacube Input")
        inp.blendernc_datacube_vars = "adt"
        bpy.ops.blendernc.datacubeload_sui()
        bpy.ops.blendernc.purge_all()

    def test_ui_remove_cache_with_cache_no_image(self):
        # Node tree exists,
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        change_file(file)
        blendernc_nodes = get_blendernc_nodetrees()
        inp = blendernc_nodes[0].nodes.get("datacube Input")
        inp.blendernc_datacube_vars = "adt"
        bpy.ops.blendernc.datacubeload_sui()
        out = blendernc_nodes[0].nodes.get("Output")
        out.update_on_frame_change = False
        nodetree_name = blendernc_nodes[0].bl_idname
        cache_nodetree = bpy.context.scene.datacube_cache[nodetree_name]
        [cache_nodetree.pop(key) for key in list(cache_nodetree.keys())]
        bpy.ops.blendernc.purge_all()

    def test_ui_remove_cache_with_cache_animate(self):
        # Node tree exists,
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        change_file(file)
        blendernc_nodes = get_blendernc_nodetrees()
        inp = blendernc_nodes[0].nodes.get("datacube Input")
        inp.blendernc_datacube_vars = "adt"
        bpy.ops.blendernc.datacubeload_sui()
        out = blendernc_nodes[0].nodes.get("Output")
        out.update_on_frame_change = True
        bpy.context.scene.frame_set(2)
        bpy.ops.blendernc.purge_all()

    def test_common_name_matching_files(self):
        filenames = ["ssh_1995-01.nc", "ssh_1995-02.nc"]
        output = findCommonName(filenames)
        self.assertEqual("ssh_1995-0*.nc", output)

    def test_common_name_2_no_matching_start(self):
        filenames = ["ssh_1995-01.nc", "ECMWF_data.grib"]
        with self.assertRaises(ValueError):
            findCommonName(filenames)

    def test_common_name_no_matching_format(self):
        filenames = ["ssh_1995-01.nc", "ssh_2000-10.grib"]
        with self.assertRaises(ValueError):
            findCommonName(filenames)

    def test_common_name_4(self):
        filenames = ["ssh_1995-01.nc", "ssh_data.nc"]
        with self.assertRaises(ValueError):
            findCommonName(filenames)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_operators)
test = unittest.TextTestRunner().run(suite)

ret = not test.wasSuccessful()
sys.exit(ret)
