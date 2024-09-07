#!/usr/bin/env python3
import importlib

import bpy

from blendernc.blendernc import registerBlenderNC, unregisterBlenderNC
from blendernc.messages import PrintMessage, required_package
from blendernc.preferences import (
    BlenderNC_Preferences,
    add_python_path,
    import_workspace,
    load_handler_for_startup,
    print_error,
)

__version__ = "0.6.0"


from . import addon_updater_ops

bl_info = {
    "name": "BlenderNC",
    "author": "Oriol Tintó Prims & Josué Martínez-Moreno",
    "description": "Blender Add-On to visualize geo-scientific data",
    "blender": (2, 83, 0),
    "version": (0, 6, 0),
    "location": "View3D",
    "warning": "Early version",
    "category": "Science",
    "License": "MIT",
    "doc_url": "https://blendernc.readthedocs.io/en/docs/",
    "tracker_url": "https://github.com/blendernc/blendernc/issues/",
}


def register():
    """
    register Register all BlenderNC functions into Blender
    """
    # Update addon by CGCookie
    addon_updater_ops.register(bl_info)
    bpy.utils.register_class(BlenderNC_Preferences)
    # Load blendernc only at launching blender.
    registerBlenderNC()
    # Add python path to sys.path specified in the add-on preferences.
    add_python_path()
    prefs = bpy.context.preferences.addons.get("blendernc").preferences
    if importlib.find_loader("xarray"):
        print("Registering to Change Defaults")
        bpy.app.handlers.load_factory_startup_post.append(import_workspace)
        bpy.app.handlers.load_factory_startup_post.append(load_handler_for_startup)

    elif "__addon_persistent" in globals():
        PrintMessage(required_package, title="Error", icon="ERROR", edit_text="xarray")
    elif hasattr(prefs, "blendernc_python_path"):
        if prefs.blendernc_python_path:
            import sys

            sys.path.append(prefs.blendernc_python_path)
        else:
            bpy.app.handlers.load_factory_startup_post.append(print_error)
    else:
        bpy.app.handlers.load_factory_startup_post.append(print_error)


def unregister():
    """
    unregister Unregister all BlenderNC functions into Blender
    """
    # Update addon by CGCookie
    addon_updater_ops.unregister()
    unregisterBlenderNC()
    bpy.utils.unregister_class(BlenderNC_Preferences)
    if (
        importlib.find_loader("xarray")
        and load_handler_for_startup in bpy.app.handlers.load_factory_startup_post
    ):
        print("Unregistering to Change Defaults")
        bpy.app.handlers.load_factory_startup_post.remove(load_handler_for_startup)
        bpy.app.handlers.load_factory_startup_post.remove(import_workspace)

    elif print_error in bpy.app.handlers.load_post:
        bpy.app.handlers.load_factory_startup_post.remove(print_error)
