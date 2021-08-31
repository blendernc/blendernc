#!/usr/bin/env python3
# Imports
from collections import defaultdict

import bpy

from blendernc.core.update_ui import update_value_and_node_tree
from blendernc.decorators import NodesDecorators
from blendernc.python_functions import rotate_longitude


class BlenderNC_NT_rotatelon(bpy.types.Node):
    # === Basics ===
    # Description string
    """NetCDF loading resolution"""
    # Optional identifier string. If not explicitly defined,
    # the python class name is used.
    bl_idname = "datacubeRotatelon"
    # Label for nice name display
    bl_label = "Rotate Longitude"
    # Icon identifier
    bl_icon = "MESH_GRID"
    blb_type = "NETCDF"

    blendernc_rotation: bpy.props.FloatProperty(
        name="Degrees to rotate",
        default=0,
        step=1,
        precision=0,
        update=update_value_and_node_tree,
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
        layout.prop(self, "blendernc_rotation")

    # Detail buttons in the sidebar.
    # If this function is not defined,
    # the draw_buttons function is used instead
    def draw_buttons_ext(self, context, layout):
        pass

    # Optional: custom label
    # Explicit user label overrides this,
    # but here we can define a label dynamically
    def draw_label(self):
        return "Rotate Longitude"

    @NodesDecorators.node_connections
    def update(self):
        rotate_longitude(self, bpy.context)
