import unittest

import bpy
import test_utils as tutils


def test_no_selected_file(node_list=[], node_args=None):
    node_groups = bpy.data.node_groups
    if tutils.is_blendernc_in_nodetree(node_groups):
        node_groups.remove(node_groups["BlenderNC"])

    bpy.data.node_groups.new("BlenderNC", "BlenderNC")

    # Create nodes
    nodes = []
    for node in node_list[:]:
        nodes.append(node)

    node_names = tutils.create_nodes(nodes)

    print("Testing nodes:")
    print(*nodes)

    node_tree = bpy.data.node_groups["BlenderNC"]
    existing_nodes = [node_tree.nodes[node] for node in node_names]
    # Now let's change properties.
    props = tutils.build_dict_blendernc_prop(existing_nodes)

    if node_args:
        for key, args in node_args.items():
            props[key] = args

    tutils.join_nodes(node_tree, existing_nodes, props)


class Test_expected_errors(unittest.TestCase):
    def test_node_no_file(self):
        nodes = ["netCDFPath", "netCDFNode"]
        test_no_selected_file(nodes)
        # self.assertRaises(ExpectedException, test_no_selected_file, nodes)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_expected_errors)
test = unittest.TextTestRunner().run(suite)

ret = not test.wasSuccessful()
sys.exit(ret)
