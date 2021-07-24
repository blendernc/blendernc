#!/usr/bin/env python3
# Imports
from collections import defaultdict

import bpy
import nodeitems_utils

from .handlers import update_all_images
from .nodes.cmaps.cmapsnode import (
    BLENDERNC_CMAPS_NT_node,
    BlenderNC_MT_avail_colormaps,
    BlenderNC_OT_select_colormap,
)
from .nodes.grid.BlenderNC_NT_input_grid import BlenderNC_NT_input_grid
from .nodes.grid.BlenderNC_NT_resolution import BlenderNC_NT_resolution
from .nodes.grid.BlenderNC_NT_rotate_lon import BlenderNC_NT_rotatelon
from .nodes.inputs.BlenderNC_NT_datacube import BlenderNC_NT_datacube
from .nodes.inputs.BlenderNC_NT_path import BlenderNC_NT_path
from .nodes.inputs.BlenderNC_NT_range import BlenderNC_NT_range
from .nodes.inputs.BlenderNC_NT_tutorial import BlenderNC_NT_tutorial
from .nodes.math.BlenderNC_NT_derivatives import BlenderNC_NT_derivatives
from .nodes.math.BlenderNC_NT_math import BlenderNC_NT_math
from .nodes.math.BlenderNC_NT_transpose import BlenderNC_NT_transpose
from .nodes.node_categories import node_categories
from .nodes.node_tree import BlenderNCNodeTree, node_tree_name
from .nodes.outputs.BlenderNC_NT_output import BlenderNC_NT_output
from .nodes.outputs.BlenderNC_NT_preloader import BlenderNC_NT_preloader
from .nodes.selecting.BlenderNC_NT_drop_dims import BlenderNC_NT_drop_dims
from .nodes.selecting.BlenderNC_NT_select_axis import BlenderNC_NT_select_axis
from .nodes.selecting.BlenderNC_NT_select_time import BlenderNC_NT_select_time
from .nodes.selecting.BlenderNC_NT_sort import BlenderNC_NT_sort
from .nodes.shortcuts.BlenderNC_NT_basic_nodes import BlenderNC_NT_basic_nodes

# TODO: Uncomment after fixing issue with Python header.
# from .nodes.vectors.BlenderNC_NT_line_int_conv import BlenderNC_NT_lic
from .operators import (
    BlenderNC_OT_apply_material,
    BlenderNC_OT_colorbar,
    BlenderNC_OT_compute_range,
    BlenderNC_OT_datacube2img,
    BlenderNC_OT_datacubeload,
    BlenderNC_OT_preloader,
    BlenderNC_OT_var,
)
from .panels import (
    BlenderNC_dask_client,
    BlenderNC_UI_PT_file_selection,
    BlenderNC_UI_PT_parent,
    BlenderNC_workspace_animation,
    BlenderNC_workspace_memory,
    BlenderNC_workspace_panel,
)
from .sockets import bNCdatacubeSocket, bNCfloatSocket, bNCstringSocket
from .UI_operators import (
    BlenderNC_OT_purge_all,
    BlenderNC_OT_Simple_UI,
    Import_OT_mfdataset,
    ImportDatacubeCollection,
)

# from . nodes import BlenderNC_NT_datacube, BlenderNC_NT_preloader,\
#                     BlenderNC_NT_resolution, BlenderNC_NT_output,\
#                     BlenderNC_NT_select_axis, BlenderNC_NT_path


classes = [
    # Panels
    BlenderNC_UI_PT_parent,
    BlenderNC_UI_PT_file_selection,
    BlenderNC_workspace_panel,
    BlenderNC_workspace_animation,
    BlenderNC_workspace_memory,
    BlenderNC_dask_client,
    # Nodes
    BlenderNC_NT_path,
    BlenderNC_NT_datacube,
    BlenderNC_NT_range,
    BlenderNC_NT_tutorial,
    BlenderNC_NT_resolution,
    BlenderNC_NT_rotatelon,
    BlenderNC_NT_input_grid,
    BlenderNC_NT_select_axis,
    BlenderNC_NT_select_time,
    BlenderNC_NT_drop_dims,
    BlenderNC_NT_sort,
    BlenderNC_NT_math,
    BlenderNC_NT_transpose,
    BlenderNC_NT_derivatives,
    BlenderNC_NT_preloader,
    BlenderNC_NT_output,
    # Vectors
    # TODO: Uncomment after fixing issue with Python header.
    # BlenderNC_NT_lic,
    # Nodes shortcuts
    BlenderNC_NT_basic_nodes,
    # Shader Nodes
    BlenderNC_MT_avail_colormaps,
    BlenderNC_OT_select_colormap,
    BLENDERNC_CMAPS_NT_node,
    # Operators
    BlenderNC_OT_datacubeload,
    BlenderNC_OT_var,
    BlenderNC_OT_datacube2img,
    BlenderNC_OT_preloader,
    BlenderNC_OT_apply_material,
    BlenderNC_OT_compute_range,
    BlenderNC_OT_colorbar,
    # Operators: UI
    BlenderNC_OT_Simple_UI,
    BlenderNC_OT_purge_all,
    # Operators: files
    ImportDatacubeCollection,
    Import_OT_mfdataset,
    # Sockets
    bNCdatacubeSocket,
    bNCstringSocket,
    bNCfloatSocket,
]


classes.append(BlenderNCNodeTree)

handlers = bpy.app.handlers


def registerBlenderNC():
    bpy.types.Scene.update_all_images = update_all_images
    bpy.types.Scene.datacube_cache = defaultdict(None)
    # Register handlers
    handlers.frame_change_pre.append(bpy.types.Scene.update_all_images)
    handlers.render_pre.append(bpy.types.Scene.update_all_images)

    # Register node categories
    nodeitems_utils.register_node_categories(node_tree_name, node_categories)

    for cls in classes:
        bpy.utils.register_class(cls)

    return {"FINISHED"}


def unregisterBlenderNC():
    del bpy.types.Scene.update_all_images
    del bpy.types.Scene.datacube_cache

    # Delete from handlers
    handlers.frame_change_pre.remove(update_all_images)
    handlers.render_pre.remove(update_all_images)

    nodeitems_utils.unregister_node_categories(node_tree_name)

    for cls in classes:
        bpy.utils.unregister_class(cls)

    return {"FINISHED"}
