import sys
import unittest

import bpy

from blendernc.preferences import get_addon_preference


class Test_Addon(unittest.TestCase):
    def test_addon_enabled(self):
        bpy.ops.preferences.addon_enable(module="blendernc")
        blendernc_preferences = get_addon_preference()
        self.assertIsNotNone(blendernc_preferences)

    def test_addon_disable(self):
        bpy.ops.preferences.addon_disable(module="blendernc")
        isenabled = "blendernc" not in bpy.context.preferences.addons.keys()
        self.assertTrue(isenabled)

    def test_change_preferences_workspace(self):
        bpy.ops.preferences.addon_enable(module="blendernc")
        blendernc_preferences = get_addon_preference()
        preference_change = [blendernc_preferences.blendernc_workspace]
        # Change workspace to None:
        blendernc_preferences.blendernc_workspace = "NONE"
        # Restart blender:
        bpy.ops.wm.read_homefile()
        preference_change.append(blendernc_preferences.blendernc_workspace)
        # Change workspace to Only Create Workspace:
        blendernc_preferences.blendernc_workspace = "ONLY CREATE WORKSPACE"
        # Restart blender:
        bpy.ops.wm.read_homefile()
        preference_change.append(blendernc_preferences.blendernc_workspace)
        # Change workspace to Only Create Workspace:
        blendernc_preferences.blendernc_workspace = "INITIATE WITH WORKSPACE"
        # Restart blender:
        bpy.ops.wm.read_homefile()
        preference_change.append(blendernc_preferences.blendernc_workspace)
        expected_change = [
            "ONLY CREATE WORKSPACE",
            "NONE",
            "ONLY CREATE WORKSPACE",
            "INITIATE WITH WORKSPACE",
        ]
        self.assertEqual(preference_change, expected_change)

    def test_change_preferences_shading(self):
        bpy.ops.preferences.addon_enable(module="blendernc")
        blendernc_preferences = get_addon_preference()
        preference_change = [blendernc_preferences.blendernc_workspace_shading]
        # Change workspace to Only Create Workspace:
        blendernc_preferences.blendernc_workspace_shading = "RENDERED"
        # Restart blender:
        bpy.ops.wm.read_homefile()
        preference_change.append(blendernc_preferences.blendernc_workspace_shading)
        # Change workspace to Only Create Workspace:
        blendernc_preferences.blendernc_workspace_shading = "MATERIAL"
        # Restart blender:
        bpy.ops.wm.read_homefile()
        preference_change.append(blendernc_preferences.blendernc_workspace_shading)
        expected_change = ["SOLID", "RENDERED", "MATERIAL"]
        self.assertEqual(preference_change, expected_change)


# we have to manually invoke the test runner here, as we cannot use the CLI
suite = unittest.defaultTestLoader.loadTestsFromTestCase(
    Test_Addon,
)
test = unittest.TextTestRunner().run(suite)

ret = not test.wasSuccessful()
sys.exit(ret)
