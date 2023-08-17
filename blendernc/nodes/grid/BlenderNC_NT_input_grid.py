#!/usr/bin/env python3
# Imports
from collections import defaultdict

import bpy

from blendernc.core.update_ui import update_lims
from blendernc.decorators import NodesDecorators
from blendernc.get_utils import get_dims, get_new_identifier, get_var


def get_possible_grid(node, context):
    datacubefile = node.persistent_dict
    if not datacubefile or "Dataset" not in node.persistent_dict.keys():
        return []
    datacubedata = node.persistent_dict["Dataset"]
    items = get_var(
        datacubedata,
        str_filter=["x", "y", "z", "time", "lat", "lon", "depth", "geolon", "geolat"],
    )
    dims = get_dims(datacubedata, start_c=len(items) - 1)
    return items + dims


class BlenderNC_NT_input_grid(bpy.types.Node):
    # === Basics ===
    # Description string
    """Select axis"""
    # Optional identifier string. If not explicitly defined,
    # the python class name is used.
    bl_idname = "datacubeInputGrid"
    # Label for nice name display
    bl_label = "Input Grid"
    # Icon identifier
    bl_icon = "SNAP_GRID"
    blb_type = "NETCDF"

    blendernc_file: bpy.props.StringProperty()
    """An instance of the original StringProperty."""

    blendernc_grid_x: bpy.props.EnumProperty(
        items=get_possible_grid,
        name="Select X grid",
        # update=dict_update,
    )
    """An instance of the original EnumProperty."""

    blendernc_grid_y: bpy.props.EnumProperty(
        items=get_possible_grid, name="Select Y grid"
    )
    """An instance of the original EnumProperty."""

    change_axeslim: bpy.props.BoolProperty(
        name="Change plot limits", default=False, update=update_lims
    )
    """An instance of the original BoolProperty."""

    blendernc_xgrid_max: bpy.props.FloatProperty(name="max", default=0)
    """An instance of the original FloatProperty."""

    blendernc_xgrid_min: bpy.props.FloatProperty(name="min", default=0)
    """An instance of the original FloatProperty."""

    blendernc_ygrid_max: bpy.props.FloatProperty(name="max", default=0)
    """An instance of the original FloatProperty."""

    blendernc_ygrid_min: bpy.props.FloatProperty(name="min", default=0)
    """An instance of the original FloatProperty."""

    # Dataset requirements
    blendernc_dataset_identifier: bpy.props.StringProperty()
    """An instance of the original StringProperty."""
    blendernc_dict = defaultdict(None)
    # Deep copy of blender dict to extract variables.
    persistent_dict = defaultdict(None)

    # === Optional Functions ===
    # Initialization function, called when a new node is created.
    def init(self, context):
        self.width = 200
        self.inputs.new("bNCstringSocket", "Path")
        self.outputs.new("bNCdatacubeSocket", "Grid")
        self.blendernc_dataset_identifier = get_new_identifier(self) + "_g"
        self.blendernc_file = None

    # Copy function to initialize a copied node from an existing one.
    def copy(self, node):
        print("Copying from node ", node)

    # Free function to clean up on removal.
    def free(self):
        self.blendernc_dict.pop(self.blendernc_dataset_identifier, None)
        print("Removing node ", self, ", Goodbye!")

    # Additional buttons displayed on the node.
    def draw_buttons(self, context, layout):
        layout.label(text="Select grid:")
        layout.label(text="X grid:")
        layout.prop(self, "blendernc_grid_x", text="")
        if self.change_axeslim:
            layout.label(text="X lims:")
            row = layout.row(align=True)
            row.prop(self, "blendernc_xgrid_min", text="min")
            row.prop(self, "blendernc_xgrid_max", text="max")
        layout.label(text="Y grid:")
        layout.prop(self, "blendernc_grid_y", text="")
        if self.change_axeslim:
            layout.label(text="Y lims:")
            row = layout.row(align=True)
            row.prop(self, "blendernc_ygrid_min", text="min")
            row.prop(self, "blendernc_ygrid_max", text="max")
        layout.prop(self, "change_axeslim")

    # Detail buttons in the sidebar.
    # If this function is not defined,
    # the draw_buttons function is used instead
    def draw_buttons_ext(self, context, layout):
        pass

    # Optional: custom label
    # Explicit user label overrides this,
    # but here we can define a label dynamically
    def draw_label(self):
        return "Grid Import"

    @NodesDecorators.node_connections
    def update(self):
        if self.persistent_dict != "":
            self.persistent_dict = self.blendernc_dict.copy()
        unique_identifier = self.blendernc_dataset_identifier

        unique_data_dict_node = self.blendernc_dict[unique_identifier]
        dataset = unique_data_dict_node["Dataset"]
        if self.blendernc_grid_x and self.blendernc_grid_y:
            unique_data_dict_node["Dataset"] = dataset.get(
                [self.blendernc_grid_x, self.blendernc_grid_y]
            )
            unique_data_dict_node["Coords"] = {
                "X": self.blendernc_grid_x,
                "Y": self.blendernc_grid_y,
            }
