#!/usr/bin/env python3
# Imports
from collections import defaultdict

import bpy

from blendernc.core.update_ui import (
    UpdateImage,
    update_colormap_interface,
    update_value,
)
from blendernc.decorators import NodesDecorators
from blendernc.image import dataset_2_image_preview


class BlenderNC_NT_output(bpy.types.Node):
    # === Basics ===
    # Description string
    """NetCDF loading resolution"""
    # Optional identifier string. If not explicitly defined,
    # the python class name is used.
    bl_idname = "datacubeOutput"
    # Label for nice name display
    bl_label = "Output"
    # Icon identifier
    bl_icon = "RENDER_RESULT"
    blb_type = "NETCDF"

    update_on_frame_change: bpy.props.BoolProperty(
        name="Update on frame change",
        default=False,
    )
    """An instance of the original BoolProperty."""

    image: bpy.props.PointerProperty(
        type=bpy.types.Image,
        name="",
        update=update_value,
    )
    """An instance of the original PointerProperty."""

    frame_loaded: bpy.props.IntProperty(
        default=-1,
    )
    """An instance of the original IntProperty."""

    frame: bpy.props.IntProperty(
        default=1,
    )
    """An instance of the original IntProperty."""

    keep_nan: bpy.props.BoolProperty(
        name="Replace nan with zeros",
        default=True,
    )
    """An instance of the original BoolProperty."""

    grid_node_name: bpy.props.StringProperty()
    """An instance of the original StringProperty."""

    # Dataset requirements
    blendernc_dataset_identifier: bpy.props.StringProperty()
    """An instance of the original StringProperty."""
    blendernc_dict = defaultdict(None)

    # === Optional Functions ===
    # Initialization function, called when a new node is created.
    # This is the most common place to create the sockets for a node,
    # as shown below.
    def init(self, context):
        self.frame_loaded = -1
        self.inputs.new("bNCdatacubeSocket", "Dataset")
        self.color = (0.8, 0.4, 0.4)
        self.use_custom_color = True

    # Copy function to initialize a copied node from an existing one.
    def copy(self, node):
        if hasattr(self.image, "copy"):
            copied_image = self.image.copy()
            self.image = copied_image
        print("Copying from node ", node)

    # Free function to clean up on removal.
    def free(self):
        self.blendernc_dict.pop(self.blendernc_dataset_identifier, None)
        print("Removing node ", self, ", Goodbye!")

    # Additional buttons displayed on the node.
    def draw_buttons(self, context, layout):
        identifier = self.blendernc_dataset_identifier
        # Generated image supported by bpy to display,
        # but perhaps show a preview of field?
        layout.template_ID_preview(
            self,
            "image",
            new="image.new",
            open="image.open",
            rows=2,
            cols=3,
        )
        if self.image:
            is_custom_image = self.image.preview.is_image_custom
            blender_dict_keys = self.blendernc_dict.keys()
            if self.image.is_float and (
                not is_custom_image and identifier in blender_dict_keys
            ):
                image_preview = dataset_2_image_preview(self)
                self.image.preview.image_pixels_float[0:] = image_preview

        if self.image and identifier in blender_dict_keys:
            layout.prop(self, "update_on_frame_change")

            layout.prop(self, "keep_nan")

            operator = layout.operator(
                "blendernc.colorbar",
                icon="GROUP_VCOL",
            )
            operator.node = self.name
            operator.node_group = self.rna_type.id_data.name
            operator.image = self.image.name

        self.draw_grid_input()

    def draw_grid_input(self):
        node_names = self.rna_type.id_data.nodes.keys()
        if "Input Grid" in node_names and len(self.inputs) == 1:
            self.inputs.new("bNCdatacubeSocket", "Grid")
        elif "Input Grid" not in node_names and len(self.inputs) == 2:
            self.inputs.remove(self.inputs.get("Grid"))

    # Detail buttons in the sidebar.
    # If this function is not defined,
    # the draw_buttons function is used instead
    def draw_buttons_ext(self, context, layout):
        pass
        # TODO: Implement manual purge.
        # layout.label(text="INFO: Purge all frames", icon='INFO')
        # operator = layout.operator("blendernc.purge_all",
        #                             icon='GROUP_VCOL')

    # Optional: custom label
    # Explicit user label overrides this,
    # but here we can define a label dynamically
    def draw_label(self):
        return "Image Output"

    @NodesDecorators.node_connections
    def update(self):
        node_tree = self.rna_type.id_data.name

        if self.image:
            UpdateImage(
                bpy.context,
                self.name,
                node_tree,
                bpy.context.scene.frame_current,
                self.image.name,
            )
            if self.image.users >= 3:
                update_colormap_interface(self.name, node_tree)
