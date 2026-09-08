#!/usr/bin/env python3
from collections import defaultdict

from bpy.props import StringProperty
from bpy.types import NodeSocketFloat


class bNCSocketDefault:
    """Base class for all Sockets"""

    color = (0.38, 0.85, 0, 1)

    def unlink(self, link):
        return self.id_data.links.remove(link)


class bNCdatacubeSocket(NodeSocketFloat, bNCSocketDefault):
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
    display_shape = "SQUARE"

    def init(self, context):
        pass

    def draw(self, context, layout, node, text):
        layout.label(text=text)

    def draw_color(self, context, node):
        return self.color
