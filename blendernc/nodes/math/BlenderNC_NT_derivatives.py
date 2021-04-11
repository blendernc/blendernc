#!/usr/bin/env python3
# Imports
from collections import defaultdict

import bpy

from ....blendernc.msg_errors import unselected_nc_file, unselected_nc_var


class BlenderNC_NT_derivatives(bpy.types.Node):
    # === Basics ===
    # Description string
    """Select axis """
    # Optional identifier string. If not explicitly defined, the python class name is used.
    bl_idname = "netCDFderivative"
    # Label for nice name display
    bl_label = "Derivate"
    # Icon identifier
    bl_icon = "MESH_GRID"
    blb_type = "NETCDF"

    # Dataset requirements
    blendernc_dataset_identifier: bpy.props.StringProperty()
    blendernc_dict = defaultdict(None)

    # === Optional Functions ===
    # Initialization function, called when a new node is created.
    # This is the most common place to create the sockets for a node, as shown below.
    # NOTE: this is not the same as the standard __init__ function in Python, which is
    #       a purely internal Python method and unknown to the node system!
    def init(self, context):
        self.inputs.new("bNCnetcdfSocket", "Dataset")
        self.outputs.new("bNCnetcdfSocket", "Dataset")

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

    def update(self):
        unique_identifier = self.blendernc_dataset_identifier
        unique_data_dict_node = self.blendernc_dict[unique_identifier]

        if self.inputs[0].is_linked and self.inputs[0].links:
            unique_identifier = self.inputs[0].links[0].from_socket.unique_identifier
            nc_dict = self.inputs[0].links[0].from_socket.dataset.copy()
            if unique_identifier == "" or not len(nc_dict.keys()):
                unique_identifier = self.inputs[0].links[0].from_node.unique_identifier
                nc_dict = self.inputs[0].links[0].from_node.blendernc_dict.copy()

            # Check that nc_dict contains at least an unique identifier
            if unique_identifier in nc_dict.keys():
                unique_data_dict_node = nc_dict[unique_identifier].copy()
                # Check if user has selected a variable
                if "selected_var" not in unique_data_dict_node.keys():
                    bpy.context.window_manager.popup_menu(
                        unselected_nc_var, title="Error", icon="ERROR"
                    )
                    self.inputs[0].links[0].from_socket.unlink(self.inputs[0].links[0])
                    return
                # dataset = unique_data_dict_node["Dataset"]
                # sel_var = unique_data_dict_node["selected_var"]
                # var_name = sel_var["selected_var_name"]

                #####################
                # OPERATION HERE!!! #
                #####################
            else:
                bpy.context.window_manager.popup_menu(
                    unselected_nc_file, title="Error", icon="ERROR"
                )
                self.inputs[0].links[0].from_socket.unlink(self.inputs[0].links[0])
        else:
            if unique_identifier in self.blendernc_dict.keys():
                self.blendernc_dict.pop(unique_identifier)

        if self.outputs.items():
            if self.outputs[0].is_linked and self.inputs[0].is_linked:
                self.outputs[0].dataset[
                    unique_identifier
                ] = unique_data_dict_node.copy()
                self.outputs[0].unique_identifier = unique_identifier
