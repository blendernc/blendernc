#!/usr/bin/env python3
# Imports
import bpy
from nodeitems_utils import NodeCategory

# Blender Classes
node_tree_name = "BlenderNC"


class BlenderNCNodeTree(bpy.types.NodeTree):
    # Description string
    """A custom node tree type that will show up in the editor type list"""
    # Optional identifier string. If not explicitly defined,
    # the python class name is used.
    bl_idname = node_tree_name
    # Label for nice name display
    bl_label = "BlenderNC"
    # Icon identifier
    bl_icon = "WORLD"


class BlenderNCCustomTreeNode:
    pass


class BlenderNCNodeCategory(NodeCategory):
    @classmethod
    def poll(cls, context):
        # TODO: Select default node by using the node_tree_name
        return context.space_data.tree_type == node_tree_name
