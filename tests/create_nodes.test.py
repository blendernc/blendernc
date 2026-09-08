import sys
import unittest

import bpy
import numpy as np

from blendernc.node_utils import create_geometrynodetree, create_node

BlenderNCNode = np.unique(
    [
        cls.bl_idname
        for cls in bpy.types.Node.__subclasses__()
        if hasattr(cls, "bl_idname")
    ]
)


class test_add_and_remove_all_nodes(unittest.TestCase):
    def test_create_all_nodes(self):
        node_tree = create_geometrynodetree("BLENDERNC")
        for node_id in BlenderNCNode:
            create_node(node_tree, node_id, location=(0, 0), return_if_exists=True)

    def test_delete_all_nodes(self):
        if "BLENDERNC" in bpy.data.node_groups.keys():
            node_tree = bpy.data.node_groups.get("BLENDERNC")
            for node in list(node_tree.nodes):
                node_tree.nodes.remove(node)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(test_add_and_remove_all_nodes)
test = unittest.TextTestRunner().run(suite)

ret = not test.wasSuccessful()
sys.exit(ret)
