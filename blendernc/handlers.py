#!/usr/bin/env python3
import bpy
from bpy.app.handlers import persistent

from .nodes.node_tree import create_new_node_tree


@persistent
def update_all_images(scene):
    nodes = []
    if create_new_node_tree:
        node_trees = [ii for ii in bpy.data.node_groups if ii.bl_idname == "BlenderNC"]
    else:
        materials = bpy.data.materials
        node_trees = [material.node_tree for material in materials]

    # Find all nodes
    for nt in node_trees:
        for node in nt.nodes:
            nodes.append(node)

    operator = bpy.ops.BlenderNC.nc2img
    for node in nodes:
        if not node.name.count("Output"):
            continue
        if not node.update_on_frame_change:
            continue

        frame = scene.frame_current
        # node.frame = frame

        if frame == node.frame_loaded:
            continue
        node_name = node.name
        node_group = node.rna_type.id_data.name
        # flip = node.flip
        image = node.image.name
        operator(node=node_name, node_group=node_group, frame=frame, image=image)
        node.frame_loaded = frame


# TODO Implement update_time as a handler
# @persistent
# def update_time(scene):
#     time = bpy.context.scene.frame_current
#     #TODO allow user to define format.

#     if 'Camera' in bpy.data.objects.keys() and time:
#         Camera = bpy.data.objects.get('Camera')
#         size = 0.03
#         coords = (-0.35,0.17,-1)
#         children_name  = [children.name for children in  Camera.children]
#         if "BlenderNC_time" not in children_name:
#             font_curve = bpy.ops.object.text_add(radius=size)
#             text=bpy.context.object
#             text.name="BlenderNC_time"
#             text.parent = Camera
#             text.location = coords
#             try:
#             # Add material
#                 text.data.materials.append(mat)
#             except:
#                 pass
#         else:
#             childrens = Camera.children
#             text = [child for child in childrens if child.name=="BlenderNC_time"][-1]
#         text.data.body = str(time)
#         if text.select_get():
#             text.select_set(False)
