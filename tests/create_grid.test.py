import sys
import unittest

import bpy

from blendernc.node_utils import create_blenderncnodetree


class test_create_grid(unittest.TestCase):
    def test_create_all_nodes(self):
        node_tree = create_blenderncnodetree("BLENDERNC")


suite = unittest.defaultTestLoader.loadTestsFromTestCase(test_create_grid)
test = unittest.TextTestRunner().run(suite)

ret = not test.wasSuccessful()
sys.exit(ret)
