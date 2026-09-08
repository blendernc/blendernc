import bpy
import logging

from .operators import (
    Import_OT_mfdataset,
    Import_OT_CreateGrid,
    )

from .menus import (
    BlenderNCNodeAnimate,
    BlenderNCNodeGrid,
    BlenderNCNodeImport,
    BlenderNCNodeMenu,
    add_custom_node_to_menu,
)

from .panels import (
    BlenderNC_UI_PT_3D_VIEW_PARENT,
    BlenderNC_UI_PT_3D_VIEW,
)

from .nodes import (
    DatacubeImport,
    DatacubeVariable,
    DatacubeCoords,
    DatacubeGrid,
    DatacubeSlice,
    DatacubeSelect,
    DatacubeAnimateTexture,
    DebugNode,
)

from .menus import (
    BlenderNCNodeMenu,
    BlenderNCNodeImport,
    BlenderNCNodeSelection,
    BlenderNCNodeGrid,
    BlenderNCNodeAnimate,
    add_custom_node_to_menu
)

from .sockets import ( 
    bNCdatacubeSocket 
)

from .properties import (
    BNC_data,
)

classes = [BNC_data,
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

def register():
    logging.info("Registering BlenderNC")
    # Register node categories
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.NODE_MT_add.append(add_custom_node_to_menu)
    return {"FINISHED"}


def unregister():
    logging.info("Un-registering BlenderNC")
    # Unregister node categories
    for cls in classes:
        bpy.utils.unregister_class(cls)

    bpy.types.NODE_MT_add.remove(add_custom_node_to_menu)
    return {"FINISHED"}