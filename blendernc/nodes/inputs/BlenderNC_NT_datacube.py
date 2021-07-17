#!/usr/bin/env python3
# Imports
from collections import defaultdict

import bpy

from blendernc.decorators import NodesDecorators
from blendernc.get_utils import get_new_identifier, get_possible_variables
from blendernc.python_functions import dict_update


class BlenderNC_NT_datacube(bpy.types.Node):
    # === Basics ===
    # Description string
    """Node to initiate datacube dataset using xarray"""
    # Optional identifier string. If not explicitly defined,
    # he python class name is used.
    bl_idname = "datacubeNode"
    # Label for nice name display
    bl_label = "datacube Input"
    # Icon identifier
    bl_icon = "UGLYPACKAGE"
    bl_type = "NETCDF"

    blendernc_file: bpy.props.StringProperty()
    """An instance of the original StringProperty."""

    blendernc_datacube_vars: bpy.props.EnumProperty(
        items=get_possible_variables,
        name="Select Variable",
        update=dict_update,
    )
    """An instance of the original EnumProperty."""

    # Note that this dictionary is in shared memory.
    blendernc_dict = defaultdict()
    blendernc_dataset_identifier: bpy.props.StringProperty()
    """An instance of the original StringProperty."""

    # === Optional Functions ===
    # Initialization function, called when a new node is created.
    # This is the most common place to create the sockets for a node,
    # as shown below.
    def init(self, context):
        self.inputs.new("bNCstringSocket", "Path")
        self.outputs.new("bNCdatacubeSocket", "Dataset")
        self.blendernc_dataset_identifier = get_new_identifier(self)
        self.color = (0.4, 0.8, 0.4)
        self.use_custom_color = True

    # Copy function to initialize a copied node from an existing one.
    def copy(self, node):
        self.blendernc_dataset_identifier = get_new_identifier(self)
        print("Copying from node ", node)

    # Free function to clean up on removal.
    def free(self):
        self.blendernc_dict.pop(self.blendernc_dataset_identifier, None)
        print("Removing node ", self, ", Goodbye!")

    # Additional buttons displayed on the node.
    def draw_buttons(self, context, layout):
        layout.label(text="Select Variable:")
        layout.prop(self, "blendernc_datacube_vars", text="")

    # Detail buttons in the sidebar.
    # If this function is not defined,
    # the draw_buttons function is used instead
    def draw_buttons_ext(self, context, layout):
        layout.label(text="Select Variable:")
        pass

    # Optional: custom label
    # Explicit user label overrides this,
    # but here we can define a label dynamically
    def draw_label(self):
        if self.blendernc_dataset_identifier not in self.blendernc_dict.keys():
            return "datacube Input"
        else:
            return self.blendernc_file.split("/")[-1]

    @NodesDecorators.node_connections
    def update(self):
        identifier = self.blendernc_dataset_identifier
        blendernc_dict = self.blendernc_dict[identifier]
        updated_dataset = blendernc_dict["Dataset"][
            self.blendernc_datacube_vars
        ].to_dataset()

        # Note, only this node will have access to the socket.
        # All the following nodes will pass directly to the next node.
        self.outputs[0].dataset[identifier] = blendernc_dict.copy()
        self.outputs[0].dataset[identifier]["Dataset"] = updated_dataset.copy()
        self.outputs[0].unique_identifier = identifier
        # Check decorators before modifying anything here.
