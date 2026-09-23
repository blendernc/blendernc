import sys
import unittest


class Test_import_mfdataset(unittest.TestCase):
    def test_import_mfdataset(self):
        pass


suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_import_mfdataset)
test = unittest.TextTestRunner().run(suite)

ret = not test.wasSuccessful()
sys.exit(ret)
