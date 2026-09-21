#!/usr/bin/env python3
# Imports
import bpy


class BlenderNCNodeTree(bpy.types.NodeTree):
    # Description string
    """A custom node tree type that will show up in the editor type list"""
    # Optional identifier string. If not explicitly defined,
    # the python class name is used.
    bl_idname = "BlenderNCNodeTree"
    # Label for nice name display
    bl_label = "BlenderNC"
    # Icon identifier
    bl_icon = "WORLD"
