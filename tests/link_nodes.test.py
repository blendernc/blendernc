import sys
import unittest

import os

from blendernc.node_utils import create_geometrynodetree, create_nodes, create_links


class Test_nodes(unittest.TestCase):
    def test_create_basic_nodes(self):
        global nodes_dict

        nodes_dict = {"BlenderNCNodeImport":{},
                 "BlenderNCNodeCoords":{},
                 "BlenderNCNodeVariable":{},
                 "BlenderNCNodeSlice":{},
                 "BlenderNCNodeGrid":{},
                }
        
        node_tree = create_geometrynodetree("BLENDERNC")
        nodes_dict = create_nodes(node_tree,nodes_dict)
        node_import = nodes_dict["BlenderNCNodeImport"]["node"]
        node_import.datacube_file = os.path.abspath("./dataset/ssh_1995-01.nc")

        datastruct = node_import.BNC_datastructs[0]

        datastruct_dict_exists = datastruct.dict[datastruct.filename] is not None
        self.assertTrue(datastruct_dict_exists)

    def test_link_input_and_coords(self):
        global nodes_dict
        node_tree = create_geometrynodetree("BLENDERNC")

        nodes_dict["BlenderNCNodeImport"]["links"] = {"xarray datacube":{"BlenderNCNodeCoords":"xarray datacube"}}

        create_links(node_tree,nodes_dict)

        coord_node = nodes_dict["BlenderNCNodeCoords"]["node"]
        datastruct = coord_node.BNC_datastructs[0]
        dataset = datastruct.dict[datastruct.filename]

        socket_coords = [socket.name for socket in coord_node.outputs]
        self.assertEqual(list(dataset.coords), socket_coords)

suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_nodes)
test = unittest.TextTestRunner().run(suite)

ret = not test.wasSuccessful()
sys.exit(ret)
