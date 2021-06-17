#!/usr/bin/env python3

from .blendernc import registerBlenderNC, unregisterBlenderNC

bl_info = {
    "name": "BlenderNC",
    "author": "Oriol Tintó Prims & Josué Martínez-Moreno",
    "description": "Blender Add-On to visualize geo-scientific data",
    "blender": (2, 83, 0),
    "version": (0, 2, 0),
    "location": "View3D",
    "warning": "Early version",
    "category": "Generic",
    "License": "MIT",
}


def register():
    registerBlenderNC()


def unregister():
    unregisterBlenderNC()
