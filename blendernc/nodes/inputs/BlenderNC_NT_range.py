#!/usr/bin/env python3
# Imports
from collections import defaultdict

import bpy

import blendernc.core.update_ui as bnc_updateUI
from blendernc.decorators import NodesDecorators


class BlenderNC_NT_range(bpy.types.Node):
    # === Basics ===
    # Description string
    """Select axis"""
    # Optional identifier string. If not explicitly defined,
    # the python class name is used.
    bl_idname = "datacubeRange"
    # Label for nice name display
    bl_label = "datacube Range"
    # Icon identifier
    bl_icon = "OUTLINER"
    blb_type = "NETCDF"

    blendernc_dataset_min: bpy.props.FloatProperty(
        name="vmin", default=0, update=bnc_updateUI.update_range
    )
    """An instance of the original FloatProperty."""
    blendernc_dataset_max: bpy.props.FloatProperty(
        name="vmax", default=1, update=bnc_updateUI.update_range
    )
    """An instance of the original FloatProperty."""

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
        layout.label(text="Select:")
        layout.prop(self, "blendernc_dataset_min")
        layout.prop(self, "blendernc_dataset_max")
        layout.label(text="or")
        operator = layout.operator(
            "blendernc.compute_range",
            icon="DRIVER_DISTANCE",
        )
        operator.node = self.name
        operator.node_group = self.rna_type.id_data.name

    # Detail buttons in the sidebar.
    # If this function is not defined,
    # the draw_buttons function is used instead
    def draw_buttons_ext(self, context, layout):
        pass

    # Optional: custom label
    # Explicit user label overrides this,
    # but here we can define a label dynamically
    def draw_label(self):
        return "Range"

    @NodesDecorators.node_connections
    def update(self):
        unique_identifier = self.blendernc_dataset_identifier
        unique_data_dict_node = self.blendernc_dict[unique_identifier]
        sel_var = unique_data_dict_node["selected_var"]
        # Update vmax and vmin of the dataset.
        sel_var["max_value"] = self.blendernc_dataset_max
        sel_var["min_value"] = self.blendernc_dataset_min
