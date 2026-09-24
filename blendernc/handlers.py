#!/usr/bin/env python3
from bpy.app.handlers import persistent

from .node_utils import get_all_nodes_by_idname
from .utils import add_attribute, find_coord_matches, get_data_from_datastruct


@persistent
def bNC_update_attributes(scene):
    anim_text_nodes = get_all_nodes_by_idname("BlenderNCNodeAnimateTexture")
    if not anim_text_nodes:
        return

    frame = scene.frame_current

    for node in anim_text_nodes:
        variable = node.inputs.get("Variable").default_value
        object = node.inputs.get("Object").default_value
        mesh = object.data

        datastruct = node.BNC_datastructs[0]

        data = get_data_from_datastruct(datastruct, variable)
        coords = {coord: data[coord].shape for coord in data.coords}
        matched_coords = find_coord_matches(len(mesh.vertices), coords)

        animate_coord = [
            coord for coord in coords.keys() if coord not in matched_coords
        ][0]

        len_animate_coord = len(data[animate_coord])
        if frame >= len_animate_coord:
            frame = len_animate_coord - 1
            return
        elif frame < 0:
            frame = 0
            return

        var = data.isel({animate_coord: frame}).values.transpose(1, 0).flatten()

        attr = add_attribute(mesh, variable, type="FLOAT", domain="POINT")
        attr.data.foreach_set("value", var)
        # grid_node.update()
    # mesh, attr_name, type="FLOAT", domain="POINT"
