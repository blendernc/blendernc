import os
import unittest

import bpy


class Test_operators(unittest.TestCase):
    def test_ui_no_file(self):
        bpy.ops.blendernc.var(file_path="")

    def test_ui_file(self):
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        bpy.ops.blendernc.var(file_path=file)
        # self.assertRaises(ExpectedException, test_no_selected_file, nodes)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_operators)
unittest.TextTestRunner().run(suite)
