#!/usr/bin/env python3
# Imports
from collections import defaultdict

import bpy
import numpy as np

from ....blendernc.core.netcdf_metadata import *
from ....blendernc.decorators import NodesDecorators
from ....blendernc.python_functions import (
    refresh_cache,
    update_node_tree,
    update_value_and_node_tree,
)


class BlenderNC_NT_select_axis(bpy.types.Node):
    # === Basics ===
    # Description string
    """Select axis"""
    # Optional identifier string. If not explicitly defined, the python class name is used.
    bl_idname = "netCDFaxis"
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

    axis_selection: bpy.props.FloatProperty(
        name="Axis selection:",
        update=update_value_and_node_tree,
        options={"ANIMATABLE"},
    )

    pre_selected: bpy.props.FloatProperty()

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
        if (
            self.inputs[0].is_linked
            and self.inputs[0].links
            and self.blendernc_dataset_identifier
        ):
            blendernc_dict = self.inputs[0].links[0].from_node.blendernc_dict
            if blendernc_dict:
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
                    layout.label(
                        text="[{0} - {1}]".format(
                            np.round(dataset[self.axes][0].values, 2),
                            np.round(dataset[self.axes][-1].values),
                            2,
                        )
                    )
                    layout.prop(self, "axis_selection", text="")
                    layout.label(text="INFO: nearest value", icon="INFO")
                    layout.label(text="will be selected")
        # layout.label(text="INFO: Work in progress", icon='INFO')
        # layout.prop(self, "axis")

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
        if self.axes and self.axis_selection:
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
            # blendernc_dict['Dataset'] = dataset.sel(time = self.selected_time).drop('time')
