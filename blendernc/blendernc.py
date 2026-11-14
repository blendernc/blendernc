import logging

import bpy

from .decorators import flush_pending_unlinks
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
from .panels import (
    BlenderNC_NODE_PT_SETTINGS,
    BlenderNC_UI_PT_3D_VIEW,
    BlenderNC_UI_PT_3D_VIEW_PARENT,
)
from .properties import BlenderNC_Settings, BlenderNC_UI_Properties, BNC_data
from .sockets import bNCdatacubeSocket

classes = [
    BlenderNCNodeTree,
    BNC_data,
    Import_OT_mfdataset,
    Import_OT_CreateGrid,
    BlenderNCBakeFromAttribute,
    BlenderNC_UI_PT_3D_VIEW_PARENT,
    BlenderNC_UI_PT_3D_VIEW,
    BlenderNC_NODE_PT_SETTINGS,
    BlenderNC_UI_Properties,
    BlenderNC_Settings,
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

# Handler lists that run :func:`bNC_update_attributes`.
HANDLER_LISTS = ("frame_change_pre", "render_pre")


def _is_frame_handler(func):
    """Match by name and module, so a copy left by an add-on reload matches."""
    return (
        getattr(func, "__name__", None) == bNC_update_attributes.__name__
        and getattr(func, "__module__", None) == bNC_update_attributes.__module__
    )


def unregister_handlers():
    """Remove every copy of the frame handler; absent handlers are ignored."""
    for name in HANDLER_LISTS:
        handler_list = getattr(bpy.app.handlers, name)
        for func in [f for f in handler_list if _is_frame_handler(f)]:
            handler_list.remove(func)


def register_handlers():
    """Add the frame handler exactly once to each list."""
    unregister_handlers()
    for name in HANDLER_LISTS:
        getattr(bpy.app.handlers, name).append(bNC_update_attributes)


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
    register_handlers()
    # Register node categories
    logger.info("Registering BlenderNC")
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.BlenderNC_UI_Properties = bpy.props.PointerProperty(
        type=BlenderNC_UI_Properties
    )
    bpy.types.Scene.BlenderNC_Settings = bpy.props.PointerProperty(
        type=BlenderNC_Settings
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
    unregister_handlers()
    if bpy.app.timers.is_registered(flush_pending_unlinks):
        bpy.app.timers.unregister(flush_pending_unlinks)
    logger.info("Un-registering BlenderNC")
    # Unregister node categories
    for cls in classes:
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.BlenderNC_UI_Properties
    del bpy.types.Scene.BlenderNC_Settings
    bpy.types.NODE_MT_add.remove(add_custom_node_to_menu)
    return {"FINISHED"}
