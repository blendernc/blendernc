#!/usr/bin/env python3
# Imports
import bpy

from blendernc.core.update_ui import update_value_and_node_tree


class BlenderNC_NT_path(bpy.types.Node):
    # === Basics ===
    # Description string
    """Select axis"""
    # Optional identifier string. If not explicitly defined,
    # the python class name is used.
    bl_idname = "datacubePath"
    # Label for nice name display
    bl_label = "datacube Path"
    # Icon identifier
    bl_icon = "FOLDER_REDIRECT"
    blb_type = "NETCDF"

    blendernc_file: bpy.props.StringProperty(
        name="",
        description="Folder with assets blend files",
        default="",
        maxlen=1024,
        update=update_value_and_node_tree,
    )
    """An instance of the original StringProperty."""

    # === Optional Functions ===
    # Initialization function, called when a new node is created.
    # This is the most common place to create the sockets for a node,
    # as shown below.
    def init(self, context):
        self.outputs.new("bNCstringSocket", "Path")
        self.color = (0.4, 0.8, 0.4)
        self.use_custom_color = True

    # Copy function to initialize a copied node from an existing one.
    def copy(self, node):
        print("Copying from node ", node)

    # Free function to clean up on removal.
    def free(self):
        print("Removing node ", self, ", Goodbye!")

    # Additional buttons displayed on the node.
    def draw_buttons(self, context, layout):
        row = layout.row(align=True)
        split = row.split(factor=0.85, align=True)

        split.prop(self, "blendernc_file")
        operator = split.operator(
            "blendernc.import_mfdataset", text="", icon="FILEBROWSER"
        )
        operator.node = self.name
        operator.node_group = self.rna_type.id_data.name

        # TODO: Implement dask
        # row = layout.row(align=True)
        # split = row.split(factor=0.85,align=True)
        # split.label(text = "Use dask:")
        # split.prop(self, "use_dask")

    # Detail buttons in the sidebar.
    # If this function is not defined,
    # the draw_buttons function is used instead
    def draw_buttons_ext(self, context, layout):
        pass

    # Optional: custom label
    # Explicit user label overrides this,
    # but here we can define a label dynamically
    def draw_label(self):
        return "datacube Path"

    def update(self):
        if self.outputs[0].is_linked and self.blendernc_file:
            self.outputs[0].text = self.blendernc_file
