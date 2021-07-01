#!/usr/bin/env python3
# Imports
from collections import defaultdict

import bpy
import numpy as np
import xarray as xr

# TODO Fix this import
from blendernc.cython_build import lic_internal
from blendernc.decorators import NodesDecorators
from blendernc.get_utils import get_geo_coord_names
from blendernc.python_functions import refresh_cache


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
    """An instance of the original StringProperty."""
    blendernc_dict = defaultdict(None)

    # === Optional Functions ===
    # Initialization function, called when a new node is created.
    # This is the most common place to create the sockets for a node,
    # as shown below.
    def init(self, context):
        self.inputs.new("bNCnetcdfSocket", "Dataset (u)")
        self.inputs.new("bNCnetcdfSocket", "Dataset (v)")
        self.outputs.new("bNCnetcdfSocket", "Dataset")

    # Copy function to initialize a copied node from an existing one.
    def copy(self, node):
        print("Copying from node ", node)

    # Free function to clean up on removal.
    def free(self):
        print("Removing node ", self, ", Goodbye!")

    # Additional buttons displayed on the node.
    def draw_buttons(self, context, layout):
        layout.label(text="Line Integral Convolution ")

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
        frame = bpy.context.scene.frame_current
        unique_identifier = self.blendernc_dataset_identifier
        unique_data_dict_node = self.blendernc_dict[unique_identifier]
        parent_node = self.inputs[0].links[0].from_node
        dataset = parent_node.blendernc_dict[unique_identifier]["Dataset"].copy()
        # TODO: Move this condition to the decorator.
        if self.inputs[-1].links and self.inputs[0].links:
            input_from_node = self.inputs[-1].links[0].from_node
            sel_var = unique_data_dict_node["selected_var"]
            var_name = sel_var["selected_var_name"]

            dataset_other = (
                self.inputs[-1]
                .links[0]
                .from_node.blendernc_dict[input_from_node.blendernc_dataset_identifier]
            )
            varname_other = dataset_other["selected_var"]["selected_var_name"]

            dataarray_link_1 = unique_data_dict_node["Dataset"][var_name]
            dataarray_link_2 = dataset_other["Dataset"][varname_other]

            if dataarray_link_1.shape != dataarray_link_2.shape:
                raise ValueError(
                    """Both velocity fields should be the same dimensions."""
                )

            texture = np.random.rand(*dataarray_link_2.shape).astype(np.float32)

            coords_name = get_geo_coord_names(dataset)

            x_coord = dataarray_link_1[coords_name["lon_name"][0]]
            y_coord = dataarray_link_1[coords_name["lat_name"][0]]

            vector_list = [dataarray_link_1.fillna(0), dataarray_link_2.fillna(0)]

            vectors = xr.concat(vector_list, dim="vel").T.values.astype(np.float32)

            kernellen = int(0.2 * len(x_coord))
            if (kernellen % 2) == 0:
                kernellen += 1

            kernel_shift = np.sin(
                (0.5 * np.arange(kernellen) / float(kernellen) + frame)
            )

            kernel = (
                np.sin(np.arange(kernellen) * np.pi / float(kernellen)) * kernel_shift
            )

            kernel = kernel.astype(np.float32)
            # TODO: Move this function to the image production
            lic_data = lic_internal.line_integral_convolution(
                vectors,
                texture,
                kernel,
            )

            lic_dataset = xr.Dataset(
                {
                    var_name: (["lat", "lon"], lic_data.T),
                },
                coords={
                    "lon": (["lon"], x_coord),
                    "lat": (["lat"], y_coord),
                },
            )

            unique_data_dict_node["Dataset"] = lic_dataset
            NodeTree = self.rna_type.id_data.name
            identifier = self.blendernc_dataset_identifier
            refresh_cache(NodeTree, identifier, frame)
