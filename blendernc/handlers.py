#!/usr/bin/env python3
import bpy
from bpy.app.handlers import persistent

import blendernc.get_utils as bnc_gutils
import blendernc.preferences as preferences


@persistent
def update_all_images(scene):
    nodes = bnc_gutils.get_all_output_nodes()

    operator = bpy.ops.BlenderNC.datacube2img
    for node in nodes:
        not_update = not node.update_on_frame_change
        not_identif = not node.blendernc_dataset_identifier
        not_dict = node.blendernc_dataset_identifier not in node.blendernc_dict
        if not_update or not_identif or not_dict:
            continue

        frame = scene.frame_current

        if frame == node.frame_loaded:
            continue
        node_name = node.name
        node_group = node.rna_type.id_data.name
        image = node.image.name
        operator(node=node_name, node_group=node_group, frame=frame, image=image)
        node.frame_loaded = frame


@persistent
def load_handler(dummy):
    pref = preferences.get_addon_preference()
    if pref.blendernc_autoreload_datasets:
        blendernc_nodetrees = bnc_gutils.get_blendernc_nodetrees()
        for blendernc_nodetree in blendernc_nodetrees:
            for node in blendernc_nodetree.nodes:
                if node.bl_idname == "datacubeOutput":
                    node.update()
