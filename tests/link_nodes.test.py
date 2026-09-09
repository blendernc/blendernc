import os
import sys
import unittest

import bpy

from blendernc.node_utils import create_geometrynodetree, create_links, create_nodes


class Test_nodes(unittest.TestCase):
    def test_create_basic_nodes(self):
        global nodes_dict

        nodes_dict = {
            "BlenderNCNodeImport": {},
            "BlenderNCNodeCoords": {},
            "BlenderNCNodeVariable": {},
            "BlenderNCNodeSlice": {},
            "BlenderNCNodeGrid": {},
        }

        node_tree = create_geometrynodetree("BLENDERNC")
        nodes_dict = create_nodes(node_tree, nodes_dict)
        node_import = nodes_dict["BlenderNCNodeImport"]["node"]
        node_import.datacube_file = os.path.abspath("./dataset/ssh_1995-01.nc")

        datastruct = node_import.BNC_datastructs[0]

        datastruct_dict_exists = datastruct.dict[datastruct.filename] is not None
        self.assertTrue(datastruct_dict_exists)

    def test_link_input_and_coords(self):
        global nodes_dict
        node_tree = create_geometrynodetree("BLENDERNC")

        nodes_dict["BlenderNCNodeImport"]["links"] = {
            "xarray datacube": {"BlenderNCNodeCoords": "xarray datacube"}
        }

        create_links(node_tree, nodes_dict)

        coord_node = nodes_dict["BlenderNCNodeCoords"]["node"]
        datastruct = coord_node.BNC_datastructs[0]
        dataset = datastruct.dict[datastruct.filename]

        socket_coords = [socket.name for socket in coord_node.outputs]
        self.assertEqual(list(dataset.coords), socket_coords)

    def test_link_variable_and_grid(self):
        global nodes_dict
        node_tree = create_geometrynodetree("BLENDERNC")

        coords_node = nodes_dict["BlenderNCNodeCoords"]["node"]

        nodes_dict["BlenderNCNodeImport"]["links"] = {
            "xarray datacube": {"BlenderNCNodeVariable": "xarray datacube"}
        }
        nodes_dict["BlenderNCNodeCoords"]["links"] = {
            coords_node.outputs[0].name: {"BlenderNCNodeGrid": "X"},
            coords_node.outputs[1].name: {"BlenderNCNodeGrid": "Y"},
        }

        create_links(node_tree, nodes_dict)

        grid_node = nodes_dict["BlenderNCNodeGrid"]["node"]

        is_linked = grid_node.inputs[0].is_linked
        self.assertTrue(is_linked)

    # def test_xarray_grid(self):
    #     global nodes_dict
    #     node_tree = create_geometrynodetree("BLENDERNC")
    #     grid_node = nodes_dict["BlenderNCNodeGrid"]["node"]

    #     bpy.ops.blendernc.create_grid_from_coords(node_name = grid_node.name, node_tree=grid_node.id_data.name)

    #     object = grid_node.outputs['Object'].default_value.name
    #     object_exists = object in bpy.data.objects
    #     self.assertTrue(object_exists)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_nodes)
test = unittest.TextTestRunner().run(suite)

ret = not test.wasSuccessful()
sys.exit(ret)
