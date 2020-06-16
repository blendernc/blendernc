# Imports
import bpy
from collections import defaultdict

import nodeitems_utils

from . panels import BlenderNC_UI_PT_3dview, BlenderNC_LOAD_OT_On, BlenderNC_LOAD_OT_Off
from . operators import BlenderNC_OT_ncload, BlenderNC_OT_netcdf2img, BlenderNC_OT_preloader
from . nodes import BlenderNC_NT_netcdf, BlenderNC_NT_preloader,\
                    BlenderNC_NT_resolution, BlenderNC_NT_output,\
                    create_new_node_tree, BlenderNCNodeTree, \
                    node_tree_name, node_categories

classes = [
    # Panels
    BlenderNC_LOAD_OT_On,
    BlenderNC_LOAD_OT_Off,
    BlenderNC_UI_PT_3dview,
    # Nodes
    BlenderNC_NT_netcdf,
    BlenderNC_NT_preloader,
    BlenderNC_NT_resolution,
    BlenderNC_NT_output,
    # Operators
    BlenderNC_OT_ncload,
    BlenderNC_OT_netcdf2img,
    BlenderNC_OT_preloader,
]

if create_new_node_tree:
    classes.append(BlenderNCNodeTree)
from bpy.app.handlers import persistent


@persistent
def update_all_images(scene):
    print("Update images operator called at frame: %i" % bpy.context.scene.frame_current)

    nodes = []
    if create_new_node_tree:
        node_trees = bpy.data.node_groups
    else:
        materials = bpy.data.materials
        node_trees = [material.node_tree for material in materials]

    # Find all nodes
    for nt in node_trees:
        for node in nt.nodes:
            nodes.append(node)

    op = bpy.ops.BlenderNC.nc2img
    for node in nodes:
        if not node.name.count("netCDFinput"):
            continue
        if not node.update_on_frame_change:
            continue

        step = scene.frame_current
        node.step = step
        print(step, node.frame_loaded)
        if step == node.frame_loaded:
            continue
        file_name = node.file_name
        var_name = node.var_name
        flip = node.flip
        image = node.image.name
        op(file_name=file_name, var_name=var_name, step=step, flip=flip, image=image)
        node.frame_loaded = step
        print("Var %s from file %s has been updated!" % (var_name, file_name))


handlers = bpy.app.handlers


def registerBlenderNC():
    bpy.types.Scene.update_all_images = update_all_images

    bpy.types.Scene.nc_dictionary = defaultdict(None)
    bpy.types.Scene.nc_cache = defaultdict(None)
    # Register handlers
    handlers.frame_change_pre.append(bpy.types.Scene.update_all_images)
    handlers.render_pre.append(bpy.types.Scene.update_all_images)

    # Register node categories
    nodeitems_utils.register_node_categories(node_tree_name, node_categories)

    for cls in classes:
        bpy.utils.register_class(cls)


def unregisterBlenderNC():
    del bpy.types.Scene.nc_dictionary
    del bpy.types.Scene.update_all_images
    del bpy.types.Scene.nc_cache

    # Delete from handlers
    handlers.frame_change_pre.remove(update_all_images)
    handlers.render_pre.remove(update_all_images)
    # del bpy.types.Scene.nc_file_path

    nodeitems_utils.unregister_node_categories(node_tree_name)

    for cls in classes:
        bpy.utils.unregister_class(cls)
