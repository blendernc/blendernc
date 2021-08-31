#!/usr/bin/env python3
# Imports
from collections import defaultdict

import bpy

from blendernc.core.update_ui import update_value_and_node_tree
from blendernc.decorators import NodesDecorators
from blendernc.python_functions import datacube_values


class BlenderNC_NT_resolution(bpy.types.Node):
    # === Basics ===
    # Description string
    """NetCDF loading resolution"""
    # Optional identifier string. If not explicitly defined,
    # the python class name is used.
    bl_idname = "datacubeResolution"
    # Label for nice name display
    bl_label = "Resolution"
    # Icon identifier
    bl_icon = "MESH_GRID"
    blb_type = "NETCDF"

    blendernc_resolution: bpy.props.FloatProperty(
        name="Resolution",
        min=1,
        max=100,
        default=50,
        step=100,
        update=update_value_and_node_tree,
        precision=0,
        options={"ANIMATABLE"},
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
        self.color = (0.4, 0.4, 0.8)
        self.use_custom_color = True

    # Copy function to initialize a copied node from an existing one.
    def copy(self, node):
        print("Copying from node ", node)

    # Free function to clean up on removal.
    def free(self):
        print("Removing node ", self, ", Goodbye!")

    # Additional buttons displayed on the node.
    def draw_buttons(self, context, layout):
        layout.prop(self, "blendernc_resolution")

    # Detail buttons in the sidebar.
    # If this function is not defined,
    # the draw_buttons function is used instead
    def draw_buttons_ext(self, context, layout):
        pass

    # Optional: custom label
    # Explicit user label overrides this,
    # but here we can define a label dynamically
    def draw_label(self):
        return "Resolution"

    @NodesDecorators.node_connections
    def update(self):
        unique_identifier = self.blendernc_dataset_identifier
        unique_data_dict_node = self.blendernc_dict[unique_identifier]
        sel_var = unique_data_dict_node["selected_var"]
        dataset = unique_data_dict_node["Dataset"]
        var_name = sel_var["selected_var_name"]
        resolution = self.blendernc_resolution
        datacube_data = datacube_values(dataset, var_name, resolution)
        unique_data_dict_node["Dataset"] = datacube_data
        sel_var["resolution"] = resolution
        # TODO: Do I know time here if so, select time and load snapshot here
