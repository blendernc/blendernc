#!/usr/bin/env python3
from collections import defaultdict

from bpy.props import FloatProperty, StringProperty
from bpy.types import NodeSocket

socket_colors = {
    "bNCnetcdfSocket": (0.6, 1.0, 0.6, 1.0),
    "bNCpercentSocket": (0.8, 0.8, 0.8, 0.3),
}


class bNCSocketDefault:
    """Base class for all Sockets"""

    def unlink(self, link):
        return self.id_data.links.remove(link)

    def delete_dataset(self, link):
        if self.identifier == "Dataset":
            keys = list(self.dataset.keys())
            for key in keys:
                self.dataset.pop(key)


class bNCnetcdfSocket(NodeSocket, bNCSocketDefault):
    bl_idname = "bNCnetcdfSocket"
    bl_label = "netCDF Socket"

    dataset = defaultdict()
    unique_identifier: StringProperty()

    def draw(self, context, layout, node, text):
        layout.label(text=text)

    def draw_color(self, context, node):
        return (0.38, 0.85, 0.90, 1)


class bNCstringSocket(NodeSocket, bNCSocketDefault):
    bl_idname = "bNCstringSocket"
    bl_label = "String Socket"

    text: StringProperty()

    def draw(self, context, layout, node, text):
        layout.label(text=text)

    def draw_color(self, context, node):
        return (0.68, 0.85, 0.90, 1)

    def unlink(self, link):
        return self.id_data.links.remove(link)


class bNCfloatSocket(NodeSocket, bNCSocketDefault):
    bl_idname = "bNCfloatSocket"
    bl_label = "Float Socket"

    Float: FloatProperty(default=1)

    def draw(self, context, layout, node, text):
        # layout.label(text=text)
        layout.prop(self, "Float")

    def draw_color(self, context, node):
        return (0.68, 0.85, 0.90, 1)

    def unlink(self, link):
        return self.id_data.links.remove(link)
