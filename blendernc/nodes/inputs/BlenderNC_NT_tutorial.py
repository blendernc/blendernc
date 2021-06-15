#!/usr/bin/env python3
# Imports
from collections import defaultdict

import bpy

from blendernc.blendernc.decorators import NodesDecorators

from ....blendernc.python_functions import (
    dict_update,
    dict_update_tutorial_datacube,
    get_new_identifier,
    get_possible_variables,
    get_xarray_datasets,
)


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

    blendernc_xarray_datacube: bpy.props.EnumProperty(
        items=get_xarray_datasets,
        name="Select Variable",
        update=dict_update_tutorial_datacube,
    )

    blendernc_netcdf_vars: bpy.props.EnumProperty(
        items=get_possible_variables,
        name="Select Variable",
        update=dict_update,
    )

    # Dataset requirements
    blendernc_dataset_identifier: bpy.props.StringProperty()
    blendernc_dict = defaultdict(None)

    # === Optional Functions ===
    # Initialization function, called when a new node is created.
    # This is the most common place to create the sockets for a node,
    # as shown below.
    def init(self, context):
        self.blendernc_dataset_identifier = get_new_identifier(self)
        self.outputs.new("bNCnetcdfSocket", "Dataset")
        self.color = (0.4, 0.8, 0.4)
        self.use_custom_color = True

    # Copy function to initialize a copied node from an existing one.
    def copy(self, node):
        self.blendernc_dataset_identifier = get_new_identifier(self)
        print("Copying from node ", node)

    # Free function to clean up on removal.
    def free(self):
        if self.blendernc_dataset_identifier != "":
            self.blendernc_dict.pop(self.blendernc_dataset_identifier)
        print("Removing node ", self, ", Goodbye!")

    # Additional buttons displayed on the node.
    def draw_buttons(self, context, layout):
        layout.label(text="Select Datacube:")
        layout.prop(self, "blendernc_xarray_datacube", text="")
        layout.label(text="Select Variable:")
        layout.prop(self, "blendernc_netcdf_vars", text="")

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

    @NodesDecorators.node_connections
    def update(self):
        #####################
        # OPERATION HERE!!! #
        #####################
        pass
