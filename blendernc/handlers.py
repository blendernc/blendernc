#!/usr/bin/env python3
import bpy
from bpy.app.handlers import persistent

import blendernc.get_utils as bnc_gutils


@persistent
def update_all_images(scene):

    nodes = bnc_gutils.get_all_output_nodes()

    operator = bpy.ops.BlenderNC.datacube2img
    for node in nodes:
        if not node.update_on_frame_change:
            continue

        frame = scene.frame_current

        if frame == node.frame_loaded:
            continue
        node_name = node.name
        node_group = node.rna_type.id_data.name
        image = node.image.name
        operator(node=node_name, node_group=node_group, frame=frame, image=image)
        node.frame_loaded = frame
