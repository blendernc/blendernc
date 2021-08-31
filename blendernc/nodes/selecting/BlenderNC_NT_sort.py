#!/usr/bin/env python3
# Imports
from collections import defaultdict

import bpy

from blendernc.core.update_ui import update_node_tree, update_value_and_node_tree
from blendernc.decorators import DrawDecorators, NodesDecorators
from blendernc.get_utils import get_possible_dims


class BlenderNC_NT_sort(bpy.types.Node):
    # === Basics ===
    # Description string
    """Select axis"""
    # Optional identifier string. If not explicitly defined,
    # the python class name is used.
    bl_idname = "datacubeSort"
    # Label for nice name display
    bl_label = "Sortby Dimension"
    # Icon identifier
    bl_icon = "MESH_GRID"
    blb_type = "NETCDF"

    blendernc_dims: bpy.props.EnumProperty(
        items=get_possible_dims,
        name="Select Dimension",
        update=update_value_and_node_tree,
    )
    """An instance of the original EnumProperty."""

    # Dataset requirements
    blendernc_dataset_identifier: bpy.props.StringProperty()
    """An instance of the original StringProperty."""
    blendernc_dict = defaultdict(None)

    # === Optional Functions ===
    # Initialization function, called when a new node is created.
    # This is the most common place to create the sockets for a node,
    # as shown below.
    def init(self, context):
        self.inputs.new("bNCdatacubeSocket", "Dataset")
        self.outputs.new("bNCdatacubeSocket", "Dataset")

    # Copy
    def copy(self, node):
        print("Copying from node ", node)

    # Free function to clean up on removal.
    def free(self):
        print("Removing node ", self, ", Goodbye!")

    # Additional buttons displayed on the node.
    @DrawDecorators.is_connected
    def draw_buttons(self, context, layout):
        layout.prop(self, "blendernc_dims", text="")

    # Detail buttons in the sidebar.
    # If this function is not defined,
    # the draw_buttons function is used instead
    def draw_buttons_ext(self, context, layout):
        pass

    # Optional: custom label
    # Explicit user label overrides this,
    # but here we can define a label dynamically
    def draw_label(self):
        return "Sortby Dimension"

    @NodesDecorators.node_connections
    def update(self):
        blendernc_dict = self.blendernc_dict[self.blendernc_dataset_identifier]
        # Drop dimensions
        if self.blendernc_dims != "":
            dataset = blendernc_dict["Dataset"].sortby(self.blendernc_dims)

        blendernc_dict["Dataset"] = dataset
        update_node_tree(self, bpy.context)
