#!/usr/bin/env python3

from .blendernc import registerBlenderNC, unregisterBlenderNC

bl_info = {
    "name": "BlenderNC",
    "author": "Oriol Tintó Prims & Josué Martínez-Moreno",
    "description": "Blender Add-On to visualize geo-scientific data",
    "blender": (2, 83, 0),
    "version": (0, 1, 3),
    "location": "View3D",
    "warning": "Very early version",
    "category": "Generic",
    "License": "MIT",
}


def register():
    registerBlenderNC()


def unregister():
    unregisterBlenderNC()
