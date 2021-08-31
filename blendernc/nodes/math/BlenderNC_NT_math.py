#!/usr/bin/env python3
# Imports
from collections import defaultdict

import bpy
import numpy as np

from blendernc.core.update_ui import update_random_range, update_value_and_node_tree
from blendernc.decorators import MathDecorator, NodesDecorators
from blendernc.python_functions import build_enum_prop_list, refresh_cache

operation_types = {
    "float": (
        "Power",
        "Greater than",
        "Smaller than",
    ),
    "unique": ("Logarithm", "SymLog"),
    "dataset": ("Add", "Subtract", "Multiply", "Divide"),
}

ops = {
    "Add": (lambda x, y: x + y),
    "Subtract": (lambda x, y: x - y),
    "Multiply": (lambda x, y: x * y),
    "Divide": (lambda x, y: x / y),
    "Logarithm": (lambda x, y: np.log10(x)),
    "SymLog": (lambda x, y: np.sign(x) * np.log10(abs(x))),
    "Power": (lambda x, y: x ** y),
    "Greater than": (lambda x, y: x.where(x > y, 1).where(x <= y, 0)),
    "Smaller than": (lambda x, y: x.where(x < y, 1).where(x >= y, 0)),
}

operation_items = build_enum_prop_list(list(ops.keys()))


class BlenderNC_NT_math(bpy.types.Node):
    # === Basics ===
    # Description string
    """Select axis"""
    # Optional identifier string. If not explicitly defined,
    # the python class name is used.
    bl_idname = "datacubeMath"
    # Label for nice name display
    bl_label = "Math"
    # Icon identifier
    bl_icon = "FCURVE_SNAPSHOT"
    blb_type = "NETCDF"

    blendernc_operation: bpy.props.EnumProperty(
        items=operation_items,
        name="Select operation",
        update=update_value_and_node_tree,
    )
    """An instance of the original EnumProperty."""

    update_range: bpy.props.BoolProperty(
        name="Auto-update range",
        default=False,
    )
    """An instance of the original BoolProperty."""

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

    # Copy function to initialize a copied node from an existing one.
    def copy(self, node):
        print("Copying from node ", node)

    # Free function to clean up on removal.
    def free(self):
        print("Removing node ", self, ", Goodbye!")

    # Additional buttons displayed on the node.
    def draw_buttons(self, context, layout):
        layout.prop(self, "blendernc_operation", text="")
        layout.prop(self, "update_range")

    # Detail buttons in the sidebar.
    # If this function is not defined,
    # the draw_buttons function is used instead
    def draw_buttons_ext(self, context, layout):
        pass

    # Optional: custom label
    # Explicit user label overrides this, but here we can
    # define a label dynamically
    def draw_label(self):
        return "Math"

    def create_sockets(self, operation):
        link_keys = self.inputs.keys()
        if len(link_keys) == 1 and operation not in operation_types["unique"]:
            self.inputs.new("bNCfloatSocket", "Float")
        elif len(link_keys) > 1 and operation in operation_types["unique"]:
            self.inputs.remove(self.inputs[-1])
        elif (
            operation in operation_types["dataset"]
            and "Float" not in link_keys
            and not self.inputs[-1].is_linked
        ):
            self.inputs.remove(self.inputs[-1])
            self.inputs.new("bNCfloatSocket", "Float")
        elif (
            operation in operation_types["dataset"]
            and "Float" in link_keys
            and self.inputs.get("Float").is_linked
        ):
            connected_socket = self.inputs.get("Float").links[0].from_socket
            self.inputs.remove(self.inputs.get("Float"))
            self.inputs.new("bNCdatacubeSocket", "Dataset")
            node_group = self.rna_type.id_data
            node_group.links.new(self.inputs[-1], connected_socket)
        else:
            pass

    @NodesDecorators.node_connections
    def update(self):
        NodeTree = self.rna_type.id_data.name
        frame = bpy.context.scene.frame_current
        identifier = self.blendernc_dataset_identifier
        refresh_cache(NodeTree, identifier, frame)
        operation = self.blendernc_operation
        self.create_sockets(operation)
        unique_data_dict_node = self.compute_operation()
        if self.update_range:
            max_val, min_val = update_random_range(unique_data_dict_node)
            unique_data_dict_node["selected_var"]["max_value"] = max_val
            unique_data_dict_node["selected_var"]["min_value"] = min_val

    @MathDecorator.math_operation
    def compute_operation(self, data1, data2=None, name=""):
        dataset = ops[self.blendernc_operation](data1, data2)
        if type(data1) == type(data2):
            dataset = dataset.to_dataset(name=name)
            # TODO: Update the node to ensure the image will be updated.
        return dataset
