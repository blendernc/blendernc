import sys
import unittest

import bpy
import numpy as np

from blendernc.node_utils import (
    create_blenderncnodetree,
    create_links,
    create_node,
    create_nodes,
)

BlenderNCNode = np.unique(
    [
        cls.bl_idname
        for cls in bpy.types.Node.__subclasses__()
        if hasattr(cls, "bl_idname")
    ]
)


class test_add_and_remove_all_nodes(unittest.TestCase):
    """Create and delete every registered node type."""

    def test_create_all_nodes(self):
        """Every registered node type can be added to the ``BLENDERNC`` tree."""
        node_tree = create_blenderncnodetree("BLENDERNC")
        for node_id in BlenderNCNode:
            create_node(node_tree, node_id, location=(0, 0))

    def test_two_nodes_of_one_type_from_mapping(self):
        """Entries with an explicit type can share it; links use the keys."""
        material = bpy.data.materials.new("bnc_two_ranges")
        material.use_nodes = True
        tree = material.node_tree
        mapping = {
            "ShaderNodeAttribute": {"links": {"Factor": {"Map Range": "Value"}}},
            "Map Range": {
                "type": "ShaderNodeMapRange",
                "links": {"Result": {"Map Range.001": "Value"}},
            },
            "Map Range.001": {"type": "ShaderNodeMapRange"},
        }
        for _ in range(2):  # a second pass must reuse, not duplicate
            created = create_nodes(tree, mapping)
            create_links(tree, created)

        ranges = [n for n in tree.nodes if n.bl_idname == "ShaderNodeMapRange"]
        self.assertEqual(sorted(n.name for n in ranges), ["Map Range", "Map Range.001"])
        self.assertEqual(created["Map Range"]["node"].name, "Map Range")
        self.assertTrue(created["Map Range.001"]["node"].inputs["Value"].is_linked)
        link = created["Map Range.001"]["node"].inputs["Value"].links[0]
        self.assertEqual(link.from_node.name, "Map Range")
        self.assertEqual(
            sum(n.bl_idname == "ShaderNodeAttribute" for n in tree.nodes), 1
        )
        bpy.data.materials.remove(material)

    def test_mapping_is_left_unchanged(self):
        """The caller's mapping, a module constant for the panel, stays as given."""
        tree = bpy.data.node_groups.new("bnc_geometry", "GeometryNodeTree")
        mapping = {
            "GeometryNodeMeshGrid": {
                "links": {"Mesh": {"NodeGroupOutput": "Geometry"}},
            },
        }
        before = repr(mapping)
        created = create_nodes(tree, mapping)
        self.assertEqual(repr(mapping), before)
        self.assertIn("node", created["GeometryNodeMeshGrid"])
        self.assertIn("NodeGroupOutput", created)  # added for geometry trees
        create_links(tree, created)
        output = created["NodeGroupOutput"]["node"]
        self.assertTrue(output.inputs["Geometry"].is_linked)
        bpy.data.node_groups.remove(tree)

    def test_delete_all_nodes(self):
        """All nodes can be removed from the ``BLENDERNC`` tree."""
        if "BLENDERNC" in bpy.data.node_groups.keys():
            node_tree = bpy.data.node_groups.get("BLENDERNC")
            for node in list(node_tree.nodes):
                node_tree.nodes.remove(node)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(test_add_and_remove_all_nodes)
test = unittest.TextTestRunner().run(suite)

ret = not test.wasSuccessful()
sys.exit(ret)
