#!/usr/bin/env python3
import importlib

import bpy

NODE_TYPE = "ShaderNodeValToRGB"


def divide_cmap(n, step):
    return (n - 1) * (1 / (step - 1)), int((n - 1) * (256 // (step - 1)))


def update_fill_value(node, context):
    colorramp = node.node_tree.nodes.get("Color_Ramp.000").color_ramp
    colorramp.elements[0].color = node.fv_color


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

    def get_colormaps(self):
        names = self.get_cmaps()
        cmap_names = []
        counter = 0

        for key, items in names.items():
            for item in items:
                element_1 = "{}:{}".format(item, key)
                element_2 = "{}-{}".format(item, key)
                cmap_names.append((element_1, element_2, "", counter))
                counter += 1
        return cmap_names
        # [(cmaps[ii],cmaps[ii],"",ii) for ii in range(len(cmaps))]

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
