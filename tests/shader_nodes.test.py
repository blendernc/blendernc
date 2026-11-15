"""Colormap shader node and the shader helpers merged into ``shader_utils``."""

import sys
import unittest

import bpy
import matplotlib
import numpy as np

from blendernc.shader_utils import (
    FILL_VALUE_POSITION,
    UI_MATERIAL,
    add_splines,
    add_units,
    apply_colormap,
    available_colormaps,
    colorbar_material,
    decode_colormap,
    default_colormap,
    encode_colormap,
    get_colormap,
    ui_material,
)


def ramp_colors(color_ramp):
    """RGBA of every element of a Color Ramp, as an (n, 4) array."""
    return np.array([tuple(element.color) for element in color_ramp.elements])


def ramp_positions(color_ramp):
    return np.array([element.position for element in color_ramp.elements])


class TestColormapHelpers(unittest.TestCase):
    """Library lookups and Color Ramp writing, without the node."""

    def test_available_colormaps_lists_installed_libraries(self):
        """cmocean and matplotlib are listed, without reversed or cmo. copies."""
        maps = available_colormaps()
        self.assertIn("thermal", maps["cmocean"])
        self.assertIn("viridis", maps["matplotlib"])
        for names in maps.values():
            self.assertFalse([n for n in names if n.endswith("_r")])
        self.assertFalse([n for n in maps["matplotlib"] if n.startswith("cmo.")])

    def test_identifier_round_trip_and_default(self):
        """ "name:library" identifiers encode, decode and have a default."""
        identifier = encode_colormap("viridis", "matplotlib")
        self.assertEqual(decode_colormap(identifier), ("viridis", "matplotlib"))
        name, library = decode_colormap(default_colormap())
        self.assertIn(name, available_colormaps()[library])

    def test_get_colormap_reverse(self):
        """The reversed colormap starts where the original ends."""
        forward = get_colormap("matplotlib", "viridis")
        backward = get_colormap("matplotlib", "viridis", reverse=True)
        np.testing.assert_allclose(backward(0.0), forward(1.0))

    def test_apply_colormap_layout(self):
        """Fill colour at 0, then n_stops samples from just above 0 to 1."""
        material = bpy.data.materials.new("bnc_ramp_layout")
        material.use_nodes = True
        ramp = material.node_tree.nodes.new("ShaderNodeValToRGB").color_ramp
        colormap = matplotlib.colormaps["viridis"]
        fill = (1.0, 0.0, 1.0, 1.0)
        apply_colormap(ramp, colormap, 5, fill)

        positions = ramp_positions(ramp)
        expected = np.r_[0.0, FILL_VALUE_POSITION, np.linspace(0, 1, 5)[1:]]
        np.testing.assert_allclose(positions, expected, atol=1e-7)
        colors = ramp_colors(ramp)
        np.testing.assert_allclose(colors[0], fill)
        np.testing.assert_allclose(colors[-1], colormap(1.0), atol=1e-6)
        bpy.data.materials.remove(material)


class TestColormapNode(unittest.TestCase):
    """The Colormap node inside a material."""

    def setUp(self):
        self.material = bpy.data.materials.new(f"bnc_{self._testMethodName}")
        self.material.use_nodes = True
        self.tree = self.material.node_tree
        self.node = self.tree.nodes.new("cmapsNode")

    def tearDown(self):
        bpy.data.materials.remove(self.material)

    def test_new_node_has_own_group_and_default_ramp(self):
        """A new node owns a group with input, ramp and output, linked."""
        group = self.node.node_tree
        self.assertIsNotNone(group)
        self.assertEqual(self.node.colormaps, default_colormap())
        self.assertEqual(len(self.node.color_ramp.elements), self.node.n_stops + 1)
        self.assertIn("Factor", self.node.inputs)
        self.assertIn("Color", self.node.outputs)
        ramp = next(n for n in group.nodes if n.bl_idname == "ShaderNodeValToRGB")
        self.assertTrue(ramp.inputs["Factor"].is_linked)
        self.assertTrue(ramp.outputs["Color"].is_linked)

        other = self.tree.nodes.new("cmapsNode")
        self.assertIsNot(other.node_tree, group)

    def test_settings_rebuild_the_ramp(self):
        """Colormap, stop count, flip and fill colour all reach the ramp."""
        viridis = matplotlib.colormaps["viridis"]
        self.node.colormaps = "viridis:matplotlib"
        self.node.n_stops = 6
        ramp = self.node.color_ramp
        self.assertEqual(len(ramp.elements), 7)
        np.testing.assert_allclose(ramp_colors(ramp)[-1], viridis(1.0), atol=1e-6)

        self.node.fcmap = True
        np.testing.assert_allclose(ramp_colors(ramp)[-1], viridis(0.0), atol=1e-6)

        self.node.fv_color = (0.2, 0.4, 0.6, 1.0)
        fill = ramp_colors(ramp)[0]
        np.testing.assert_allclose(fill, (0.2, 0.4, 0.6, 1.0), atol=1e-6)

    def test_select_colormap_operator(self):
        """The menu's operator sets the colormap; a wrong node is reported."""
        result = bpy.ops.blendernc.select_colormap(
            material=self.material.name, node=self.node.name, colormap="ice:cmocean"
        )
        self.assertEqual(result, {"FINISHED"})
        self.assertEqual(self.node.colormaps, "ice:cmocean")
        with self.assertRaisesRegex(RuntimeError, "not found"):
            bpy.ops.blendernc.select_colormap(
                material=self.material.name, node="missing", colormap="ice:cmocean"
            )

    def test_deleting_node_removes_its_group(self):
        """Removing the node removes the group it owned."""
        group_name = self.node.node_tree.name
        self.tree.nodes.remove(self.node)
        self.assertNotIn(group_name, bpy.data.node_groups)


class TestColorbar(unittest.TestCase):
    """Colorbar material and text objects."""

    def test_colorbar_material_copies_colormap(self):
        """The colorbar material runs coordinates through a matching Colormap."""
        source_material = bpy.data.materials.new("bnc_cbar_source")
        source_material.use_nodes = True
        source = source_material.node_tree.nodes.new("cmapsNode")
        source.colormaps = "thermal:cmocean"
        source.n_stops = 8

        material = colorbar_material("bnc_cbar", source)
        nodes = material.node_tree.nodes
        colormap = next(n for n in nodes if n.bl_idname == "cmapsNode")
        self.assertEqual(colormap.colormaps, "thermal:cmocean")
        self.assertEqual(colormap.n_stops, 8)
        self.assertFalse([n for n in nodes if n.type == "BSDF_PRINCIPLED"])
        output = next(n for n in nodes if n.type == "OUTPUT_MATERIAL")
        self.assertEqual(output.inputs["Surface"].links[0].from_node.type, "EMISSION")
        self.assertTrue(colormap.inputs["Factor"].is_linked)

        self.assertIs(colorbar_material("bnc_cbar", source), material)
        bpy.data.materials.remove(material)
        bpy.data.materials.remove(source_material)

    def test_tick_labels_and_units(self):
        """n + 1 locked tick labels and one units label, parented to the bar."""
        plane = bpy.data.objects.new("bnc_cbar_plane", None)
        bpy.context.collection.objects.link(plane)
        labels = add_splines(4, plane)
        units = add_units(plane)
        self.assertEqual(len(labels), 5)
        ticks = [round(t.location.y, 2) for t in labels]
        self.assertEqual(ticks, [-1, -0.5, 0, 0.5, 1])
        self.assertTrue(all(t.parent is plane and t.type == "FONT" for t in labels))
        self.assertTrue(all(tuple(t.lock_location) == (True,) * 3 for t in labels))
        self.assertEqual(units.data.align_x, "CENTER")
        self.assertIs(units.data.materials[0], ui_material())
        nodes = ui_material().node_tree.nodes
        bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
        emission = tuple(bsdf.inputs["Emission Color"].default_value)
        self.assertEqual(emission, (1, 1, 1, 1))
        self.assertEqual(ui_material().name, UI_MATERIAL)
        for obj in labels + [units, plane]:
            bpy.data.objects.remove(obj)


suite = unittest.TestSuite(
    unittest.defaultTestLoader.loadTestsFromTestCase(case)
    for case in (TestColormapHelpers, TestColormapNode, TestColorbar)
)
test = unittest.TextTestRunner(verbosity=2).run(suite)

ret = not test.wasSuccessful()
sys.exit(ret)
