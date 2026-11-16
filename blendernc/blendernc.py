import logging

import bpy

from .decorators import flush_pending_unlinks
from .handlers import (
    bNC_apply_animated_steps,
    bNC_update_attributes,
    bNC_update_volumes,
)
from .menus import (
    BlenderNCNodeAnimate,
    BlenderNCNodeGrid,
    BlenderNCNodeImport,
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
    DatacubeVolume,
    DebugNode,
)
from .nodetree import BlenderNCNodeTree
from .operators import (
    BlenderNCBakeFromAttribute,
    Import_OT_CreateGrid,
    Import_OT_CreateVolume,
    Import_OT_mfdataset,
)
from .panels import (
    BlenderNC_NODE_PT_SETTINGS,
    BlenderNC_UI_PT_3D_VIEW,
    BlenderNC_UI_PT_3D_VIEW_PARENT,
)
from .properties import BlenderNC_Settings, BlenderNC_UI_Properties, BNC_data
from .shader_nodes import (
    BlenderNC_MT_avail_colormaps,
    BlenderNC_MT_shader_nodes,
    BlenderNC_NT_colormap,
    BlenderNC_OT_select_colormap,
    draw_shader_menu,
)
from .sockets import bNCdatacubeSocket

classes = [
    BlenderNCNodeTree,
    BNC_data,
    Import_OT_mfdataset,
    Import_OT_CreateGrid,
    Import_OT_CreateVolume,
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
    DatacubeVolume,
    DatacubeSlice,
    DatacubeSubsample,
    DatacubeResolution,
    DatacubeSelect,
    DatacubeTexture,
    DatacubeAnimateTexture,
    bNCdatacubeSocket,
    BlenderNCNodeImport,
    BlenderNCNodeSelection,
    BlenderNCNodeGrid,
    BlenderNCNodeAnimate,
    DebugNode,
    BlenderNC_MT_avail_colormaps,
    BlenderNC_OT_select_colormap,
    BlenderNC_NT_colormap,
    BlenderNC_MT_shader_nodes,
]

# Handler lists and the BlenderNC handlers they run.
HANDLERS = (
    ("frame_change_pre", bNC_update_attributes),
    ("render_pre", bNC_update_attributes),
    ("frame_change_pre", bNC_update_volumes),
    ("render_pre", bNC_update_volumes),
    ("frame_change_post", bNC_apply_animated_steps),
)


def _same_handler(func, target):
    """Match by name and module, so a copy left by an add-on reload matches."""
    return (
        getattr(func, "__name__", None) == target.__name__
        and getattr(func, "__module__", None) == target.__module__
    )


def unregister_handlers():
    """Remove every copy of BlenderNC's handlers; absent ones are ignored."""
    for name, target in HANDLERS:
        handler_list = getattr(bpy.app.handlers, name)
        for func in [f for f in handler_list if _same_handler(f, target)]:
            handler_list.remove(func)


def register_handlers():
    """Add each BlenderNC handler exactly once to its list."""
    unregister_handlers()
    for name, target in HANDLERS:
        getattr(bpy.app.handlers, name).append(target)


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
    bpy.types.NODE_MT_shader_node_add_all.append(draw_shader_menu)
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
    bpy.types.NODE_MT_shader_node_add_all.remove(draw_shader_menu)
    return {"FINISHED"}
