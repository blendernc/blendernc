#!/usr/bin/env python3
# Imports
from collections import defaultdict

import bpy

from blendernc.decorators import NodesDecorators


class BlenderNC_NT_derivatives(bpy.types.Node):
    # === Basics ===
    # Description string
    """Select axis"""
    # Optional identifier string. If not explicitly defined,
    # the python class name is used.
    bl_idname = "datacubeDerivative"
    # Label for nice name display
    bl_label = "Derivate"
    # Icon identifier
    bl_icon = "MESH_GRID"
    blb_type = "NETCDF"

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

    # Copy function to initialize a copied node from an existing one.
    def copy(self, node):
        print("Copying from node ", node)

    # Free function to clean up on removal.
    def free(self):
        print("Removing node ", self, ", Goodbye!")

    # Additional buttons displayed on the node.
    def draw_buttons(self, context, layout):
        layout.label(
            text="INFO: Currently this node only supports 2D fields.", icon="INFO"
        )

    # Detail buttons in the sidebar.
    # If this function is not defined, the draw_buttons function is used instead
    def draw_buttons_ext(self, context, layout):
        pass

    # Optional: custom label
    # Explicit user label overrides this, but here we can define a label dynamically
    def draw_label(self):
        return "Derivate"

    def update_value(self, context):
        self.update()

    @NodesDecorators.node_connections
    def update(self):
        pass
        # unique_identifier = self.blendernc_dataset_identifier
        # unique_data_dict_node = self.blendernc_dict[unique_identifier]

        #####################
        # OPERATION HERE!!! #
        #####################
