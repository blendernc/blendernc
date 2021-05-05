#!/usr/bin/env python3
# Imports
from collections import defaultdict

import bpy
import numpy as np

from ....blendernc.decorators import NodesDecorators
from ....cython_build import lic_internal


class BlenderNC_NT_lic(bpy.types.Node):
    # === Basics ===
    # Description string
    """Select axis"""
    # Optional identifier string. If not explicitly defined,
    # the python class name is used.
    bl_idname = "netCDFlic"
    # Label for nice name display
    bl_label = "LIC"
    # Icon identifier
    bl_icon = "DECORATE_DRIVER"
    blb_type = "NETCDF"

    # Dataset requirements
    blendernc_dataset_identifier: bpy.props.StringProperty()
    blendernc_dict = defaultdict(None)

    # === Optional Functions ===
    # Initialization function, called when a new node is created.
    # This is the most common place to create the sockets for a node,
    # as shown below.
    def init(self, context):
        self.inputs.new("bNCnetcdfSocket", "Dataset")
        self.inputs.new("bNCnetcdfSocket", "Dataset")
        self.outputs.new("bNCnetcdfSocket", "Dataset")

    # Copy function to initialize a copied node from an existing one.
    def copy(self, node):
        print("Copying from node ", node)

    # Free function to clean up on removal.
    def free(self):
        if self.blendernc_dataset_identifier != "":
            self.blendernc_dict.pop(self.blendernc_dataset_identifier)
        print("Removing node ", self, ", Goodbye!")

    # Additional buttons displayed on the node.
    def draw_buttons(self, context, layout):
        layout.label(text="Template", icon="INFO")

    # Detail buttons in the sidebar.
    # If this function is not defined,
    # the draw_buttons function is used instead
    def draw_buttons_ext(self, context, layout):
        pass

    # Optional: custom label
    # Explicit user label overrides this,
    # but here we can define a label dynamically
    def draw_label(self):
        return "LIC"

    @NodesDecorators.node_connections
    def update(self):
        # Replace this section by our vector vortices
        vortex_spacing = 0.5
        extra_factor = 2.0

        a = np.array([1, 0]) * vortex_spacing
        b = np.array([np.cos(np.pi / 3), np.sin(np.pi / 3)]) * vortex_spacing
        rnv = int(2 * extra_factor / vortex_spacing)
        vortices = [n * a + m * b for n in range(-rnv, rnv) for m in range(-rnv, rnv)]
        vortices = [
            (x, y)
            for (x, y) in vortices
            if -extra_factor < x < extra_factor and -extra_factor < y < extra_factor
        ]

        xs = np.linspace(-1, 1, size).astype(np.float32)[None, :]
        ys = np.linspace(-1, 1, size).astype(np.float32)[:, None]

        vectors = np.zeros((size, size, 2), dtype=np.float32)
        for (x, y) in vortices:
            rsq = (xs - x) ** 2 + (ys - y) ** 2
            vectors[..., 0] += (ys - y) / rsq
            vectors[..., 1] += -(xs - x) / rsq
        # Replace this section by our vector vortices

        kernellen = 31

        kernel = np.sin(np.arange(kernellen) * np.pi / kernellen) * (
            1 + np.sin(2 * np.pi * 5 * (np.arange(kernellen) / float(kernellen) + t))
        )

        kernel = kernel.astype(np.float32)

        lic_internal.line_integral_convolution(vectors, texture, kernel)

        # dataset = self.blendernc_dict[self.blendernc_dataset_identifier]["Dataset"]
        # var_name = self.blendernc_dict[self.blendernc_dataset_identifier][
        #     "selected_var"
        # ]["selected_var_name"]
        # self.blendernc_dict[self.blendernc_dataset_identifier][
        #     "Dataset"
        # ] = netcdf_values(dataset, var_name, self.blendernc_resolution)
        # self.blendernc_dict[self.blendernc_dataset_identifier]["selected_var"][
        #     "resolution"
        # ] = self.blendernc_resolution
