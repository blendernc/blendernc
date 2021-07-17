import sys
import unittest

import bpy


def get_node_items():
    from blendernc.nodes.node_categories import node_dicts

    node_items_list = []
    for key, item in node_dicts.items():
        for it in item["items"]:
            node_items_list.append(it)
    return node_items_list


def get_existing_nodes(nodeTree):
    existing_nodes = bpy.data.node_groups[nodeTree].nodes.items()
    return existing_nodes


def get_exiting_node_name(existing_nodes):
    return [node[-1].bl_idname for node in existing_nodes]


def node_manipulation(action):
    node_groups = bpy.data.node_groups
    node_groups_keys = node_groups.keys()

    nodeTree = "BlenderNC"

    # Persist using the same BlenderNC.
    if not node_groups_keys:
        bpy.data.node_groups.new("BlenderNC", nodeTree)
    elif nodeTree not in node_groups_keys:
        bpy.data.node_groups.new("BlenderNC", nodeTree)
    else:
        pass

    node_tree = bpy.data.node_groups[nodeTree]
    node_tree.use_fake_user = True

    enum_items = get_node_items()
    if action == "create":
        for node in enum_items:
            node_tree.nodes.new(node)

    # Update nodes
    node_tree.nodes.update()

    existing_nodes = get_existing_nodes(nodeTree)
    existing_node_names = get_exiting_node_name(existing_nodes)

    if action == "copy":
        for node in existing_nodes:
            node[-1].copy(node[-1])
            existing_node_names.append(node[-1].bl_idname)

    elif action == "delete":
        for node in existing_nodes:
            node[-1].free()
            existing_node_names.remove(node[-1].bl_idname)

    if "datacubeBasincNodes" in enum_items:
        enum_items.remove("datacubeBasincNodes")
        enum_items = enum_items + [
            "datacubePath",
            "datacubeNode",
            "datacubeResolution",
            "datacubeOutput",
        ]

    return sorted(enum_items), sorted(existing_node_names)


class Test_simple_render(unittest.TestCase):
    def test_creation_nodes(self):
        d_n, e_n = node_manipulation("create")
        # Both list must be equal
        self.assertEqual(d_n, e_n)

    def test_copying_nodes(self):
        d_n, e_n = node_manipulation("copy")
        # List should be duplicated.
        self.assertEqual(sorted(2 * d_n), e_n)

    def test_delete_nodes(self):
        d_n, e_n = node_manipulation("delete")
        # Existing list should be empty
        self.assertFalse(e_n)

    def test_two_datacube_Node_creation(self):
        node_manipulation("create")
        node_tree = bpy.data.node_groups.new("BlenderNC", "test")
        node = node_tree.nodes.new("datacubeNode")
        unique_identifier = node.blendernc_dataset_identifier
        # unique identifier must be equal to two.
        self.assertEqual(unique_identifier, "002")


# Stop unittest from sorting tests, as we expect tests to run:
# First: Create.
# Second: Copy.
# Third: Delete.
def suite():
    suite = unittest.TestSuite()
    suite.addTest(Test_simple_render("test_creation_nodes"))
    suite.addTest(Test_simple_render("test_copying_nodes"))
    suite.addTest(Test_simple_render("test_delete_nodes"))
    return suite


suite = suite()
test = unittest.TextTestRunner().run(suite)

ret = not test.wasSuccessful()
sys.exit(ret)
