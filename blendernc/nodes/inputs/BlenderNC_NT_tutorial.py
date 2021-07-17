#!/usr/bin/env python3
# Imports
from collections import defaultdict

import bpy

from blendernc.get_utils import (
    get_new_identifier,
    get_possible_variables,
    get_xarray_datasets,
)
from blendernc.python_functions import dict_update, dict_update_tutorial_datacube


class BlenderNC_NT_tutorial(bpy.types.Node):
    # === Basics ===
    # Description string
    """Select axis"""
    # Optional identifier string. If not explicitly defined,
    # the python class name is used.
    bl_idname = "Datacube_tutorial"
    # Label for nice name display
    bl_label = "Datacube tutorial"
    # Icon identifier
    bl_icon = "ASSET_MANAGER"
    blb_type = "NETCDF"

    blendernc_file: bpy.props.StringProperty()
    """An instance of the original StringProperty."""

    blendernc_xarray_datacube: bpy.props.EnumProperty(
        items=get_xarray_datasets,
        name="Select Variable",
        update=dict_update_tutorial_datacube,
    )
    """An instance of the original EnumProperty."""

    blendernc_datacube_vars: bpy.props.EnumProperty(
        items=get_possible_variables,
        name="Select Variable",
        update=dict_update,
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
        self.blendernc_dataset_identifier = get_new_identifier(self) + "_t"
        self.outputs.new("bNCdatacubeSocket", "Dataset")
        self.color = (0.4, 0.8, 0.4)
        self.use_custom_color = True

    # Copy function to initialize a copied node from an existing one.
    def copy(self, node):
        self.blendernc_dataset_identifier = get_new_identifier(self) + "_t"
        print("Copying from node ", node)

    # Free function to clean up on removal.
    def free(self):
        print("Removing node ", self, ", Goodbye!")

    # Additional buttons displayed on the node.
    def draw_buttons(self, context, layout):
        layout.label(text="Select Datacube:")
        layout.prop(self, "blendernc_xarray_datacube", text="")
        layout.label(text="Select Variable:")
        layout.prop(self, "blendernc_datacube_vars", text="")

    # Detail buttons in the sidebar.
    # If this function is not defined,
    # the draw_buttons function is used instead
    def draw_buttons_ext(self, context, layout):
        pass

    # Optional: custom label
    # Explicit user label overrides this,
    # but here we can define a label dynamically
    def draw_label(self):
        return "Datacube tutorial"

    def update(self):
        #####################
        # OPERATION HERE!!! #
        #####################
        pass
