#!/usr/bin/env python3
# Imports
from collections import defaultdict

import bpy

from blendernc.blendernc.decorators import NodesDecorators


class BlenderNC_NT_template(bpy.types.Node):
    # === Basics ===
    # Description string
    """Select axis """
    # Optional identifier string. If not explicitly defined, the python class name is used.
    bl_idname = "netCDFtemplate"
    # Label for nice name display
    bl_label = "Template"
    # Icon identifier
    bl_icon = ""
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
        if self.blendernc_dataset_identifier != "":
            self.blendernc_dict.pop(self.blendernc_dataset_identifier)
        print("Removing node ", self, ", Goodbye!")

    # Additional buttons displayed on the node.
    def draw_buttons(self, context, layout):
        layout.label(text="Template", icon="INFO")

    # Detail buttons in the sidebar.
    # If this function is not defined, the draw_buttons function is used instead
    def draw_buttons_ext(self, context, layout):
        pass

    # Optional: custom label
    # Explicit user label overrides this, but here we can define a label dynamically
    def draw_label(self):
        return "Template"

    @NodesDecorators.node_connections
    def update(self):
        #####################
        # OPERATION HERE!!! #
        #####################
        pass
