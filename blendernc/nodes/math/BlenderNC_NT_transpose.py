#!/usr/bin/env python3
# Imports
import bpy


class BlenderNC_NT_transpose(bpy.types.Node):
    # === Basics ===
    # Description string
    """Select axis"""
    # Optional identifier string. If not explicitly defined,
    # the python class name is used.
    bl_idname = "datacubeTranspose"
    # Label for nice name display
    bl_label = "Transpose"
    # Icon identifier
    bl_icon = "MESH_GRID"
    blb_type = "NETCDF"

    axis: bpy.props.EnumProperty(items=(""), name="")
    """An instance of the original EnumProperty."""

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
        layout.label(text="INFO: Work in progress", icon="INFO")
        # layout.prop(self, "axis")

    # Detail buttons in the sidebar.
    # If this function is not defined,
    # the draw_buttons function is used instead
    def draw_buttons_ext(self, context, layout):
        pass

    # Optional: custom label
    # Explicit user label overrides this,
    # but here we can define a label dynamically
    def draw_label(self):
        return "Transpose"

    def update_value(self, context):
        self.update()

    def update(self):
        pass
