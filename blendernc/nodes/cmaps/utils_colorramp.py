#!/usr/bin/env python3
import importlib

import bpy
import numpy as np

import blendernc.python_functions as bnc_pyfunc

NODE_TYPE = "ShaderNodeValToRGB"


def divide_cmap(n, step):
    return (n - 1) * (1 / (step - 1)), int((n - 1) * (256 // (step - 1)))


def update_fill_value(node, context):
    colorramp = node.node_tree.nodes.get("ColorRamp").color_ramp
    colorramp.elements[0].color = node.fv_color


def colorbar_material(node, colormap):
    materials = bpy.data.materials
    image_name = node.image.name
    blendernc_materials = [
        material
        for material in materials
        if image_name + "_" + colormap.name in material.name
    ]

    if len(blendernc_materials) != 0:
        blendernc_material = blendernc_materials[-1]
        cmap = blendernc_material.node_tree.nodes.get("Colormap")
        if cmap.colormaps == colormap.colormaps:
            cmap.update()
            return blendernc_material
    else:
        bpy.ops.material.new()
        materials = bpy.data.materials
        blendernc_material = [
            materials[material_name]
            for material_name in materials.keys()
            if "Material" in material_name
        ][-1]
        blendernc_material.name = image_name + "_" + colormap.name

    material_node_tree = blendernc_material.node_tree

    if len(material_node_tree.nodes.keys()) == 2:
        texcoord = material_node_tree.nodes.new("ShaderNodeTexCoord")
        texcoord.location = (-760, 250)
        mapping = material_node_tree.nodes.new("ShaderNodeMapping")
        mapping.location = (-580, 250)
        cmap = material_node_tree.nodes.new("cmapsNode")
        cmap.location = (-290, 250)
        emi = material_node_tree.nodes.new("ShaderNodeEmission")
        emi.location = (-290, -50)
        P_BSDF = material_node_tree.nodes.get("Principled BSDF")
        material_node_tree.nodes.remove(P_BSDF)

    else:
        texcoord = material_node_tree.nodes.get("Texture Coordinate")
        mapping = material_node_tree.nodes.get("Mapping")
        cmap = material_node_tree.nodes.get("Colormap")
        emi = material_node_tree.nodes.get("Emission")

    output = material_node_tree.nodes.get("Material Output")

    # Links
    material_link = material_node_tree.links
    material_link.new(mapping.inputs[0], texcoord.outputs[0])
    material_link.new(cmap.inputs[0], mapping.outputs[0])
    material_link.new(emi.inputs[0], cmap.outputs[0])
    material_link.new(output.inputs[0], emi.outputs[0])

    # Assign values:
    mapping.inputs["Location"].default_value = (0, -0.6, 0)
    mapping.inputs["Rotation"].default_value = (0, np.pi / 4, 0)
    mapping.inputs["Scale"].default_value = (1, 2.8, 1)

    cmap.n_stops = colormap.n_stops
    cmap.fcmap = colormap.fcmap
    cmap.colormaps = colormap.colormaps
    cmap.fv_color = colormap.fv_color

    return blendernc_material


def add_splines(n, cbar_plane, width=0.1, height=1):
    size = 1
    splines = []
    step = 2 / n
    locs = np.round(np.arange(-1, 1 + step, step), 2)
    y_rescale = 0.12
    for ii in range(n + 1):
        bpy.ops.object.text_add(radius=size)
        spline = bpy.context.object
        spline.data.align_y = "CENTER"
        spline.parent = cbar_plane
        spline.location = (1.4, locs[ii], 0)
        spline.lock_location = (True, True, True)
        spline.scale = (1.7, y_rescale, 1.2)
        spline.name = "text_{}".format(cbar_plane.name)
        mat = bnc_pyfunc.ui_material()
        spline.data.materials.append(mat)
        splines.append(spline)
    return splines


def add_units(cbar_plane):
    size = 1.5
    y_rescale = 0.12
    bpy.ops.object.text_add(radius=size)
    units = bpy.context.object
    units.data.align_y = "CENTER"
    units.data.align_x = "CENTER"
    units.parent = cbar_plane
    units.location = (0, 1.18, 0)
    units.scale = (1.7, y_rescale, 1.2)
    mat = bnc_pyfunc.ui_material()
    units.name = "text_units_{}".format(cbar_plane.name)
    units.data.materials.append(mat)
    return units


class ColorRamp(object):
    def __init__(self):
        self.cmaps = self.installed_cmaps()

    def installed_cmaps(self):
        import pkg_resources

        cmaps = []

        installed_packages = pkg_resources.working_set
        installed_packages_list = sorted([i.key for i in installed_packages])

        if "cmocean" and "matplotlib" in installed_packages_list:
            cmaps.append("cmocean")
            cmaps.append("matplotlib")
        elif "cmocean" in installed_packages_list:
            cmaps.append("cmocean")
        elif "matplotlib" in installed_packages_list:
            cmaps.append("matplotlib")
        else:
            raise ImportError("Can't import 'cmocean' or 'matplotlib.'")
            # TODO: Raise error in UI.

        return cmaps

    def get_cmaps(self):
        import importlib

        names = {}
        for maps in self.cmaps:
            cmap = importlib.import_module(maps)
            if maps == "cmocean":
                names["cmocean"] = cmap.cm.cmapnames
            if maps == "matplotlib":
                cmaps_listed = list(cmap.cm.cmaps_listed)
                cmaps_datad = list(cmap.cm.datad)
                names["matplotlib"] = cmaps_listed + cmaps_datad
        return names

    def get_cmap_values(self, cmap_module, s_cmap):
        maps = cmap_module.__name__
        if maps == "cmocean":
            cmap = cmap_module.cm.cmap_d.get(s_cmap)
        elif maps == "matplotlib":
            cmap = cmap_module.cm.get_cmap(s_cmap)
        return cmap

    def update_colormap(self, color_ramp, selected_cmap, cmap_steps):

        self.color_ramp = color_ramp

        cmap_steps = cmap_steps
        s_cmap, maps = selected_cmap

        cmap = importlib.import_module(maps)

        c_bar_elements = self.color_ramp.elements

        # Remove all items descendent to avoid missing points and
        # leave first position.
        [
            c_bar_elements.remove(element)
            for item, element in c_bar_elements.items()[::-1][:-1]
        ]

        c_bar_elements[0].color = (0, 0, 0, 1)
        c_bar_elements.new(1e-5)
        pos, value = divide_cmap(1e-5, cmap_steps)
        c_bar_elements[1].color = self.get_cmap_values(cmap, s_cmap)(value)

        for i in range(2, cmap_steps + 1):
            pos, value = divide_cmap(i, cmap_steps)
            c_bar_elements.new(pos)
            #
            c_bar_elements[i].position = pos
            c_bar_elements[i].color = self.get_cmap_values(cmap, s_cmap)(value)

    def create_group_node(self, group_name):
        self.group_name = group_name
        self.node_groups = bpy.data.node_groups
        # make sure the node-group is present
        group = self.node_groups.get(self.group_name)
        # Uncomment to create nodes only when duplicating the node.
        # This was commented as it created issues with multiple colormap nodes
        # sharing the same node output.
        # if not group:
        group = self.node_groups.new(self.group_name, "ShaderNodeTree")
        # group.use_fake_user = True
        self.group_name = group.name
        return group

    def create_colorramp(self, node_name):
        self.get_valid_evaluate_function(node_name)

    def get_valid_node(self, node_name):
        self.node_name = node_name
        self.node_groups = bpy.data.node_groups
        # make sure the node-group is present
        group = self.node_groups.get(self.group_name)
        if not group:
            group = self.node_groups.new(self.group_name, "ShaderNodeTree")
        group.use_fake_user = True

        # make sure the color_rampNode we want to use is present too
        node = group.nodes.get(self.node_name)
        if not node:
            node = group.nodes.new(NODE_TYPE)
            node.name = self.node_name

        return node

    def get_valid_evaluate_function(self, node_name):
        """
        Takes a material-group name and a Node name it expects to find.
        The node will be of type ShaderNodeValToRGB and this function
        will force its existence, then return the evaluate function.
        """
        self.node = self.get_valid_node(node_name)
        self.color_ramp = self.node.color_ramp
        self.color_ramp.evaluate(0.0)
