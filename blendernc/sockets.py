#!/usr/bin/env python3
from collections import defaultdict

from bpy.props import FloatProperty, StringProperty
from bpy.types import NodeSocket

from blendernc.core.update_ui import update_socket_and_tree

socket_colors = {
    "bNCdatacubeSocket": (0.6, 1.0, 0.6, 1.0),
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


class bNCdatacubeSocket(NodeSocket, bNCSocketDefault):
    """
    bNCdatacubeSocket datacube socket for file import

    Parameters
    ----------
    NodeSocket : bpy.type.NodeSocket
        Blender API bpy socket to generate a new socket
    bNCSocketDefault : object
        Base class for all sockets
    """

    bl_idname = "bNCdatacubeSocket"
    bl_label = "datacube Socket"

    dataset = defaultdict()
    unique_identifier: StringProperty()
    """An instance of the original StringProperty."""

    def draw(self, context, layout, node, text):
        layout.label(text=text)

    def draw_color(self, context, node):
        return (0.38, 0.85, 0.90, 1)


class bNCstringSocket(NodeSocket, bNCSocketDefault):
    """
    bNCstringSocket String socket for file import

    Parameters
    ----------
    NodeSocket : bpy.type.NodeSocket
        Blender API bpy socket to generate a new socket
    bNCSocketDefault : object
        Base class for all sockets
    """

    bl_idname = "bNCstringSocket"
    bl_label = "String Socket"

    text: StringProperty()
    """An instance of the original StringProperty."""

    def draw(self, context, layout, node, text):
        layout.label(text=text)

    def draw_color(self, context, node):
        return (0.68, 0.85, 0.90, 1)

    def unlink(self, link):
        return self.id_data.links.remove(link)


class bNCfloatSocket(NodeSocket, bNCSocketDefault):
    """
    bNCstringSocket Float socket for file import

    Parameters
    ----------
    NodeSocket : bpy.type.NodeSocket
        Blender API bpy socket to generate a new socket
    bNCSocketDefault : object
        Base class for all sockets
    """

    bl_idname = "bNCfloatSocket"
    bl_label = "Float Socket"

    Float: FloatProperty(default=1, update=update_socket_and_tree)
    """An instance of the original FloatProperty."""

    def draw(self, context, layout, node, text):
        # layout.label(text=text)
        layout.prop(self, "Float")

    def draw_color(self, context, node):
        return (0.68, 0.85, 0.90, 1)

    def unlink(self, link):
        return self.id_data.links.remove(link)
