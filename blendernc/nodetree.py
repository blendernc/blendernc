#!/usr/bin/env python3
# Imports
import bpy


class BlenderNCNodeTree(bpy.types.NodeTree):
    # Description string
    """Visualize datacubes in Blender"""
    # Optional identifier string. If not explicitly defined,
    # the python class name is used.
    bl_idname = "BlenderNCNodeTree"
    # Label for nice name display
    bl_label = "BlenderNC"
    # Icon identifier
    bl_icon = "WORLD"

    @classmethod
    def poll(cls, context):
        """Allow the tree type in every context.

        Returns
        -------
        bool
            Always ``True``.
        """
        return True
