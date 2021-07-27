#!/usr/bin/env python3
# Imports
from collections import defaultdict

import bpy

from blendernc.core.update_ui import update_node_tree, update_value_and_node_tree
from blendernc.decorators import DrawDecorators, NodesDecorators
from blendernc.get_utils import get_items_axes
from blendernc.python_functions import refresh_cache


class BlenderNC_NT_select_axis(bpy.types.Node):
    # === Basics ===
    # Description string
    """Select axis"""
    # Optional identifier string. If not explicitly defined,
    # the python class name is used.
    bl_idname = "datacubeAxis"
    # Label for nice name display
    bl_label = "Select Axis"
    # Icon identifier
    bl_icon = "MESH_GRID"
    blb_type = "NETCDF"
    bl_width_default = 200

    axes: bpy.props.EnumProperty(
        items=get_items_axes,
        name="Axis",
    )
    """An instance of the original EnumProperty."""

    axis_selection: bpy.props.FloatProperty(
        name="Axis selection:",
        update=update_value_and_node_tree,
        options={"ANIMATABLE"},
    )
    """An instance of the original FloatProperty."""

    pre_selected: bpy.props.FloatProperty()
    """An instance of the original FloatProperty."""

    # Dataset requirements
    blendernc_dataset_identifier: bpy.props.StringProperty()
    """An instance of the original StringProperty."""
    blendernc_dict = defaultdict(None)

    # === Optional Functions ===
    # Initialization function, called when a new node is created.
    # This is the most common place to create the sockets for a node, as shown below.
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
    @DrawDecorators.is_connected
    def draw_buttons(self, context, layout):
        dataset = blendernc_dict[self.blendernc_dataset_identifier]["Dataset"]
        dims = dataset[
            blendernc_dict[self.blendernc_dataset_identifier]["selected_var"][
                "selected_var_name"
            ]
        ].dims
        if len(dims) >= 2:
            layout.prop(self, "axes", text="")
        if self.axes:
            layout.label(text="Select within range:")
            min_val_axes = dataset[self.axes][0].values
            max_val_axes = dataset[self.axes][-1].values

            layout.label(text="[{0:.2f} - {1:.2f}]".format(min_val_axes, max_val_axes))
            layout.prop(self, "axis_selection", text="")
            layout.label(text="INFO: nearest value", icon="INFO")
            layout.label(text="will be selected")

    # Detail buttons in the sidebar.
    # If this function is not defined, the draw_buttons function is used instead
    def draw_buttons_ext(self, context, layout):
        pass

    # Optional: custom label
    # Explicit user label overrides this, but here we can define a label dynamically
    def draw_label(self):
        return "Select Axis"

    @NodesDecorators.node_connections
    def update(self):
        blendernc_dict = self.blendernc_dict[self.blendernc_dataset_identifier]
        dataset = blendernc_dict["Dataset"]
        node_tree = self.rna_type.id_data.name
        if self.axes:
            blendernc_dict["Dataset"] = dataset.sel(
                {self.axes: self.axis_selection}, method="nearest"
            ).drop(self.axes)
            if self.pre_selected != self.axis_selection:
                refresh_cache(
                    node_tree,
                    self.blendernc_dataset_identifier,
                    bpy.context.scene.frame_current,
                )
                update_node_tree(self, bpy.context)
                self.pre_selected = self.axis_selection
