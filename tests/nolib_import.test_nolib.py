import sys
import unittest

import bpy

from blendernc.preferences import get_addon_preference


class Test_Addon(unittest.TestCase):
    def test_addon_nolib_enabled(self):
        bpy.ops.preferences.addon_enable(module="blendernc")
        blendernc_preferences = get_addon_preference()
        self.assertIsNotNone(blendernc_preferences)

    def test_addon_nolib_disable(self):
        bpy.ops.preferences.addon_disable(module="blendernc")
        isenabled = "blendernc" not in bpy.context.preferences.addons.keys()
        self.assertTrue(isenabled)

    def test_addon_PATH_no_exist(self):
        bpy.ops.preferences.addon_enable(module="blendernc")
        blendernc_preferences = get_addon_preference()
        blendernc_preferences.blendernc_python_path = "/noexistingPATH/"

    def test_addon_PATH_exist(self):
        bpy.ops.preferences.addon_enable(module="blendernc")
        blendernc_preferences = get_addon_preference()
        blendernc_preferences.blendernc_python_path = "/bin/"
        # Duplicate path to check if it ignores it
        blendernc_preferences.blendernc_python_path = "/bin/"


# we have to manually invoke the test runner here, as we cannot use the CLI
suite = unittest.defaultTestLoader.loadTestsFromTestCase(
    Test_Addon,
)
test = unittest.TextTestRunner().run(suite)

ret = not test.wasSuccessful()
sys.exit(ret)
