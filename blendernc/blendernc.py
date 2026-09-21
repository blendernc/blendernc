import logging

import bpy

from .handlers import bNC_update_attributes
from .menus import (
    BlenderNCNodeAnimate,
    BlenderNCNodeGrid,
    BlenderNCNodeImport,
    BlenderNCNodeMenu,
    BlenderNCNodeSelection,
    add_custom_node_to_menu,
)
from .nodes import (
    DatacubeAnimateTexture,
    DatacubeCoords,
    DatacubeGrid,
    DatacubeImport,
    DatacubeSelect,
    DatacubeSlice,
    DatacubeVariable,
    DebugNode,
)
from .nodetree import BlenderNCNodeTree
from .operators import Import_OT_CreateGrid, Import_OT_mfdataset
from .panels import BlenderNC_UI_PT_3D_VIEW, BlenderNC_UI_PT_3D_VIEW_PARENT
from .properties import BNC_data
from .sockets import bNCdatacubeSocket

classes = [
    BlenderNCNodeTree,
    BNC_data,
    Import_OT_mfdataset,
    Import_OT_CreateGrid,
    BlenderNC_UI_PT_3D_VIEW_PARENT,
    BlenderNC_UI_PT_3D_VIEW,
    DatacubeImport,
    DatacubeVariable,
    DatacubeCoords,
    DatacubeGrid,
    DatacubeSlice,
    DatacubeSelect,
    DatacubeAnimateTexture,
    bNCdatacubeSocket,
    BlenderNCNodeMenu,
    BlenderNCNodeImport,
    BlenderNCNodeSelection,
    BlenderNCNodeGrid,
    BlenderNCNodeAnimate,
    DebugNode,
]

handlers = bpy.app.handlers


def register():
    logging.info("Registering handlers")
    handlers.frame_change_pre.append(bNC_update_attributes)
    handlers.render_pre.append(bNC_update_attributes)
    # Register node categories
    logging.info("Registering BlenderNC")
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.NODE_MT_add.append(add_custom_node_to_menu)
    return {"FINISHED"}


def unregister():
    logging.info("Un-registering handlers")
    handlers.frame_change_pre.remove(bNC_update_attributes)
    handlers.render_pre.remove(bNC_update_attributes)
    logging.info("Un-registering BlenderNC")
    # Unregister node categories
    for cls in classes:
        bpy.utils.unregister_class(cls)

    bpy.types.NODE_MT_add.remove(add_custom_node_to_menu)
    return {"FINISHED"}
