#!/usr/bin/env python3
import bpy

from blendernc.blendernc import registerBlenderNC, unregisterBlenderNC
from blendernc.preferences import (
    BlenderNC_Preferences,
    import_workspace,
    load_handler_for_startup,
)

__version__ = "0.4.9"

from . import addon_updater_ops

bl_info = {
    "name": "BlenderNC",
    "author": "Oriol Tintó Prims & Josué Martínez-Moreno",
    "description": "Blender Add-On to visualize geo-scientific data",
    "blender": (2, 83, 0),
    "version": tuple(int(ii) for ii in __version__.split(".")),
    "location": "View3D",
    "warning": "Early version",
    "category": "Generic",
    "License": "MIT",
}


def register():
    """
    register Register all BlenderNC functions into Blender
    """
    # Update addon by CGCookie
    addon_updater_ops.register(bl_info)
    registerBlenderNC()
    bpy.utils.register_class(BlenderNC_Preferences)
    print("Registering to Change Defaults")
    bpy.app.handlers.load_factory_startup_post.append(load_handler_for_startup)
    bpy.app.handlers.load_factory_preferences_post.append(import_workspace)
    bpy.app.handlers.load_factory_startup_post.append(import_workspace)


def unregister():
    """
    unregister Unregister all BlenderNC functions into Blender
    """
    # Update addon by CGCookie
    addon_updater_ops.unregister()
    unregisterBlenderNC()
    bpy.utils.unregister_class(BlenderNC_Preferences)
    print("Unregistering to Change Defaults")
    bpy.app.handlers.load_factory_startup_post.remove(load_handler_for_startup)
    bpy.app.handlers.load_factory_preferences_post.remove(import_workspace)
    bpy.app.handlers.load_factory_startup_post.remove(import_workspace)
