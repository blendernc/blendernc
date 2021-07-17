#!/usr/bin/env python3
# Imports
import bpy


class BlenderNC_NT_preloader(bpy.types.Node):
    # === Basics ===
    # Description string
    """A datacube node"""
    # Optional identifier string. If not explicitly defined,
    # the python class name is used.
    bl_idname = "datacubePreloadNode"
    # Label for nice name display
    bl_label = "Load datacube"
    # Icon identifier
    bl_icon = "SOUND"
    blb_type = "NETCDF"

    # TODO: This node will receive a datacube as
    # input and store all the images in disk for easier import and animation.

    # === Optional Functions ===
    # Initialization function, called when a new node is created.
    # This is the most common place to create the sockets for a node,
    # as shown below.
    def init(self, context):
        pass

    # Copy function to initialize a copied node from an existing one.
    def copy(self, node):
        print("Copying from node ", node)

    # Free function to clean up on removal.
    def free(self):
        print("Removing node ", self, ", Goodbye!")

    # Additional buttons displayed on the node.
    def draw_buttons(self, context, layout):
        # scene = context.scene
        layout.label(text="INFO: Work in progress", icon="INFO")
        # if scene.blendernc_dict:
        #     layout.prop(self, "file_name")
        # else:
        #     layout.label(text="No datacube loaded")
        # if self.file_name:
        #     layout.prop(self, "var_name")
        # if self.var_name:
        #     layout.prop(self, "frame_start")
        #     layout.prop(self, "frame_end")
        #     if self.frame_end > self.frame_start:
        #         op = layout.operator("blendernc.preloader",
        #                           icon="FILE_REFRESH",)
        #         op.file_name = self.file_name
        #         op.var_name = self.var_name
        #         op.frame_start = self.frame_start
        #         op.frame_end = self.frame_end
        #     else:
        #         layout.label(text="Cannot preload!")

    # Detail buttons in the sidebar.
    # If this function is not defined,
    # the draw_buttons function is used instead
    def draw_buttons_ext(self, context, layout):
        pass

    # Optional: custom label
    # Explicit user label overrides this,
    # but here we can define a label dynamically
    def draw_label(self):
        return "Load datacube"

    def update_value(self, context):
        self.update()

    def update(self):
        pass
