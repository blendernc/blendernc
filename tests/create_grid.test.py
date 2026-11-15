import sys
import unittest

from blendernc.node_utils import create_blenderncnodetree


class test_create_grid(unittest.TestCase):
    """Smoke test for node tree creation."""

    def test_create_all_nodes(self):
        """Creating the ``BLENDERNC`` node tree must not raise."""
        create_blenderncnodetree("BLENDERNC")


suite = unittest.defaultTestLoader.loadTestsFromTestCase(test_create_grid)
test = unittest.TextTestRunner().run(suite)

ret = not test.wasSuccessful()
sys.exit(ret)
