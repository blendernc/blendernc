#!/usr/bin/env python3
from bpy.app.handlers import persistent

from .node_utils import get_all_nodes_by_idname
from .utils import (
    field_to_point_values,
    find_coord_matches,
    get_data_from_datastruct,
    write_point_attribute,
)


@persistent
def bNC_update_attributes(scene):
    """Write the current frame of each animated variable onto its mesh.

    Registered as a ``frame_change_pre`` and ``render_pre`` handler. For every
    "Datacube Animate Texture" node, the variable is sliced along the
    coordinate that does not match the mesh vertex count and the result is
    stored in a per-point float attribute named after the variable.

    Parameters
    ----------
    scene : bpy.types.Scene
        Scene whose ``frame_current`` selects the slice.
    """
    anim_text_nodes = get_all_nodes_by_idname("BlenderNCNodeAnimateTexture")
    if not anim_text_nodes:
        return

    for node in anim_text_nodes:
        variable = node.inputs.get("Variable").default_value
        obj = node.inputs.get("Object").default_value
        mesh = obj.data

        datastruct = node.BNC_datastructs[0]

        data = get_data_from_datastruct(datastruct, variable)
        # Only dimensions count: selected levels survive as scalar coordinates
        # and 2-D coordinates span the grid on their own, so neither may be
        # mistaken for an axis of the mesh.
        sizes = {dim: data.sizes[dim] for dim in data.dims}
        matches = find_coord_matches(len(mesh.vertices), sizes)
        grid_dims = set(matches[0]) if matches else set()
        animate_dims = [dim for dim in data.dims if dim not in grid_dims]
        if not animate_dims:
            continue

        animate_coord = animate_dims[0]
        last = data.sizes[animate_coord] - 1
        frame = min(max(scene.frame_current, 0), last)

        values = field_to_point_values(data.isel({animate_coord: frame}))
        write_point_attribute(mesh, variable, values)
