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
from .node_utils import enable_node_updates
from .nodes import (
    DatacubeAnimateTexture,
    DatacubeCoords,
    DatacubeGrid,
    DatacubeImport,
    DatacubeResolution,
    DatacubeSelect,
    DatacubeSlice,
    DatacubeSubsample,
    DatacubeTexture,
    DatacubeVariable,
    DebugNode,
)
from .nodetree import BlenderNCNodeTree
from .operators import (
    BlenderNCBakeFromAttribute,
    Import_OT_CreateGrid,
    Import_OT_mfdataset,
)
from .panels import BlenderNC_UI_PT_3D_VIEW, BlenderNC_UI_PT_3D_VIEW_PARENT
from .properties import BlenderNC_UI_Properties, BNC_data
from .sockets import bNCdatacubeSocket

classes = [
    BlenderNCNodeTree,
    BNC_data,
    Import_OT_mfdataset,
    Import_OT_CreateGrid,
    BlenderNCBakeFromAttribute,
    BlenderNC_UI_PT_3D_VIEW_PARENT,
    BlenderNC_UI_PT_3D_VIEW,
    BlenderNC_UI_Properties,
    DatacubeImport,
    DatacubeVariable,
    DatacubeCoords,
    DatacubeGrid,
    DatacubeSlice,
    DatacubeSubsample,
    DatacubeResolution,
    DatacubeSelect,
    DatacubeTexture,
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

logger = logging.getLogger(__name__)


def register():
    """Register BlenderNC with Blender.

    Adds the frame-change and render handlers, registers every class in
    ``classes``, attaches the UI property group to ``bpy.types.Scene`` and
    extends the node editor "Add" menu.

    Returns
    -------
    set
        ``{"FINISHED"}`` once registration is complete.
    """
    logger.info("Registering handlers")
    handlers.frame_change_pre.append(bNC_update_attributes)
    handlers.render_pre.append(bNC_update_attributes)
    # Register node categories
    logger.info("Registering BlenderNC")
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.BlenderNC_UI_Properties = bpy.props.PointerProperty(
        type=BlenderNC_UI_Properties
    )
    bpy.types.NODE_MT_add.append(add_custom_node_to_menu)
    enable_node_updates(True)
    return {"FINISHED"}


def unregister():
    """Remove everything that :func:`register` added to Blender.

    Returns
    -------
    set
        ``{"FINISHED"}`` once every class, handler and menu entry is removed.
    """
    # Blender re-runs every node's update() while classes are unregistered;
    # at quit time Python's thread pools are already gone, so skip the work.
    enable_node_updates(False)
    logger.info("Un-registering handlers")
    handlers.frame_change_pre.remove(bNC_update_attributes)
    handlers.render_pre.remove(bNC_update_attributes)
    logger.info("Un-registering BlenderNC")
    # Unregister node categories
    for cls in classes:
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.BlenderNC_UI_Properties
    bpy.types.NODE_MT_add.remove(add_custom_node_to_menu)
    return {"FINISHED"}
