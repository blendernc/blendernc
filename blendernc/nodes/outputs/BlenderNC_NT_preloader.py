#!/usr/bin/env python3
# Imports
from collections import defaultdict

import bpy
import numpy as np

from blendernc.core.update_ui import (  # UpdateImage,
    update_value,
    update_value_and_node_tree,
)
from blendernc.decorators import NodesDecorators
from blendernc.image import dataset_2_image_preview


class BlenderNC_NT_preloader(bpy.types.Node):
    # === Basics ===
    # Description string
    """A datacube node"""
    # Optional identifier string. If not explicitly defined,
    # the python class name is used.
    bl_idname = "datacubePreload"
    # Label for nice name display
    bl_label = "Output images"
    # Icon identifier
    bl_icon = "PASTEDOWN"
    blb_type = "NETCDF"

    update_on_frame_change: bpy.props.BoolProperty(
        name="Update on frame change",
        default=True,
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

    output_file: bpy.props.StringProperty(
        name="",
        description="Output folder",
        default="",
        maxlen=1024,
        update=update_value_and_node_tree,
    )
    """An instance of the original StringProperty."""

    max_frame: bpy.props.IntProperty(name="End:", min=1, default=250)
    """An instance of the original FloatProperty."""

    min_frame: bpy.props.IntProperty(name="Start:", min=1, default=1)
    """An instance of the original FloatProperty."""

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
        row = layout.row(align=True)
        split = row.split(factor=0.85, align=True)

        split.prop(self, "output_file")
        operator = split.operator("blendernc.export_path", text="", icon="FILEBROWSER")
        operator.node = self.name
        operator.node_group = self.rna_type.id_data.name

        frame_end = bpy.context.scene.frame_end

        # layout.label(text="[{0} - {1}]".format(frame_start, frame_end))
        layout.label(text="Frames to bake:")
        row = layout.row(align=True)
        row.prop(self, "min_frame", text="Start")
        row.prop(self, "max_frame", text="End")

        zeros_name = int(np.floor(np.log10(frame_end)) + 1)  # Order of mag + 1

        if self.image:
            is_custom_image = self.image.preview.is_image_custom
            blender_dict_keys = self.blendernc_dict.keys()
            if self.image.is_float and (
                not is_custom_image and identifier in blender_dict_keys
            ):
                image_preview = dataset_2_image_preview(self)
                self.image.preview.image_pixels_float[0:] = image_preview

        if self.image and identifier in blender_dict_keys:

            bake_operator = layout.operator(
                "blendernc.bake_image",
                icon="OUTPUT",
            )

            bake_operator.node = self.name
            bake_operator.node_group = self.rna_type.id_data.name
            bake_operator.output_path = self.output_file
            bake_operator.min_frame = self.min_frame
            bake_operator.max_frame = self.max_frame
            bake_operator.zeros_name = zeros_name
            bake_operator.image = self.image.name

            # TODO: Add an operator to bake frames.

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

    # Optional: custom label
    # Explicit user label overrides this,
    # but here we can define a label dynamically
    def draw_label(self):
        return "Output images"

    @NodesDecorators.node_connections
    def update(self):
        pass
        # node_tree = self.rna_type.id_data.name
        # if self.image:
        #     UpdateImage(
        #         bpy.context,
        #         self.name,
        #         node_tree,
        #         bpy.context.scene.frame_current,
        #         self.image.name,
        #     )
