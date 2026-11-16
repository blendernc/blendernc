#!/usr/bin/env python3
import bpy
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


class bNCAnySocket(bpy.types.NodeSocket):
    """Input socket that takes a link from an output of any type.

    Used by the Debug node, which only displays what arrives. It holds no
    value of its own, so nothing is copied into it.
    """

    bl_idname = "bNCAnySocket"
    bl_label = "Any"

    def draw(self, context, layout, node, text):
        """Draw the socket label."""
        layout.label(text=text)

    def draw_color(self, context, node):
        """Return a neutral grey, so it does not read as a datacube socket."""
        return (0.6, 0.6, 0.6, 1.0)
