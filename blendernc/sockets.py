#!/usr/bin/env python3
from bpy.types import NodeSocketFloat


class bNCSocketDefault:
    """Base class for all Sockets"""

    color = (0.38, 0.85, 0, 1)


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
        """Initialise the socket; nothing to set up."""
        pass

    def draw(self, context, layout, node, text):
        """Draw the socket label."""
        layout.label(text=text)

    def draw_color(self, context, node):
        """Return the RGBA colour used to draw the socket."""
        return self.color
