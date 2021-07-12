#!/usr/bin/env python3
import bpy
from bpy.app.handlers import persistent

from blendernc.translations import translate


@persistent
def update_all_images(scene):
    nodes = []

    node_trees = [ii for ii in bpy.data.node_groups if ii.bl_idname == "BlenderNC"]

    # Find all nodes
    for nt in node_trees:
        for node in nt.nodes:
            nodes.append(node)

    operator = bpy.ops.BlenderNC.nc2img
    for node in nodes:
        if not node.name.count(translate("Output")):
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
