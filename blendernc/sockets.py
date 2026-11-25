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


# Colour Blender's default theme gives string sockets.
STRING_SOCKET_COLOR = (0.44, 0.70, 1.0, 1.0)


class bNCVariableOrDatacubeSocket(bpy.types.NodeSocket):
    """Input socket taking a link from a variable or a datacube output.

    Used by the Slice node, which decides what it accepts and reads the
    variable name from the linked output; the socket holds no value. Its
    label and colour follow what is linked.
    """

    bl_idname = "bNCVariableOrDatacubeSocket"
    bl_label = "Variable or datacube"

    def _linked_idname(self):
        """Type of the output linked to this socket, or ``""``."""
        return self.links[0].from_socket.bl_idname if self.is_linked else ""

    def draw(self, context, layout, node, text):
        """Name what is linked: a variable, a datacube, or either."""
        labels = {
            "NodeSocketString": "Variable",
            "bNCdatacubeSocket": "xarray datacube",
        }
        layout.label(text=labels.get(self._linked_idname(), self.bl_label))

    def draw_color(self, context, node):
        """Take the colour of the linked socket; grey when nothing is linked."""
        colors = {
            "NodeSocketString": STRING_SOCKET_COLOR,
            "bNCdatacubeSocket": bNCSocketDefault.color,
        }
        return colors.get(self._linked_idname(), (0.6, 0.6, 0.6, 1.0))


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
