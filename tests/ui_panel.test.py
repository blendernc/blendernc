"""Drive the 3D view panel properties the way a user would and check the tree.

The panel builds the ``BLENDERNC`` node tree from scene properties. These
tests set those properties directly: choosing a variable before any axis
must not raise, choosing it after X and Y bakes the grid and links the
texture node, deselecting unlinks it again, and typing a step switches the
resolution node to manual and rebakes a coarser grid.
"""

import shutil
import sys
import tempfile
import unittest

import bpy
import numpy as np
import xarray as xr

NX, NY = 12, 8
VARIABLE = "noise"
NO_SELECTION = "No var"


class TestUIPanel(unittest.TestCase):
    """Scene property callbacks behind the BlenderNC sidebar panel."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp(prefix="blendernc_ui_")
        cls.path = f"{cls.tmpdir}/xy.nc"
        rng = np.random.default_rng(1)
        xr.Dataset(
            {VARIABLE: (("Y", "X"), rng.standard_normal((NY, NX)))},
            coords={"X": np.arange(float(NX)), "Y": np.arange(float(NY))},
        ).to_netcdf(cls.path)
        cls.props = bpy.context.scene.BlenderNC_UI_Properties
        cls.props.datacube_file = cls.path
        cls.tree = bpy.data.node_groups["BLENDERNC"]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def node(self, label):
        node = self.tree.nodes.get(label)
        self.assertIsNotNone(node, f"{label} missing from the panel tree")
        return node

    def test_1_variable_before_axes_does_not_raise(self):
        """No axis linked yet: selecting a variable must not bake or crash."""
        self.props.variable = VARIABLE
        self.assertNotIn("Grid", bpy.data.objects)
        texture = self.node("Datacube Texture")
        self.assertFalse(texture.inputs["Object"].is_linked)

    def test_2_variable_after_axes_bakes_and_links_texture(self):
        """With X and Y chosen the grid is baked and the texture written."""
        self.props.X = "X"
        self.props.Y = "Y"
        self.props.variable = NO_SELECTION
        self.props.variable = VARIABLE

        obj = bpy.data.objects["Grid"]
        self.assertEqual(len(obj.data.vertices), NX * NY)
        texture = self.node("Datacube Texture")
        self.assertTrue(texture.inputs["Object"].is_linked)
        self.assertTrue(texture.inputs["Variable"].is_linked)
        self.assertEqual(texture.message, "")
        self.assertIn(VARIABLE, obj.data.attributes)

    def test_3_deselect_unlinks_texture_and_removes_attribute(self):
        """Choosing the empty entry removes both links and the attribute."""
        self.props.variable = NO_SELECTION
        texture = self.node("Datacube Texture")
        self.assertFalse(texture.inputs["Object"].is_linked)
        self.assertFalse(texture.inputs["Variable"].is_linked)
        self.assertNotIn(VARIABLE, bpy.data.objects["Grid"].data.attributes)

    def test_4_manual_step_rebakes_coarser_grid(self):
        """Typing a step turns suggestions off and strides both axes."""
        resolution = self.node("Datacube Resolution")
        self.assertTrue(resolution.suggested_step)
        self.props.step = 3
        self.assertFalse(resolution.suggested_step)
        self.assertEqual(resolution.step, 3)
        obj = bpy.data.objects["Grid"]
        expected = len(range(0, NX, 3)) * len(range(0, NY, 3))
        self.assertEqual(len(obj.data.vertices), expected)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestUIPanel)
test = unittest.TextTestRunner(verbosity=2).run(suite)

ret = not test.wasSuccessful()
sys.exit(ret)
