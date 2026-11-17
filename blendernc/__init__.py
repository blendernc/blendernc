#!/usr/bin/env python3
from .blendernc import register as BNC_register
from .blendernc import unregister as BNC_unregister

##############################################################################
# .                                 IMPORTANT                                #
##############################################################################
#     This file is only used for unit testing and should not be used in      #
# production. It is not part of the BlenderNC extension and is not intended  #
#   to be used by end users. It is only used for testing purposes and may be #
#                  removed in future versions of BlenderNC.                  #
##############################################################################
##############################################################################

__version__ = "0.10.0"

bl_info = {
    "name": "BlenderNC",
    "author": "Oriol Tintó Prims & Josué Martínez-Moreno",
    "description": "Blender Add-On to visualize geo-scientific data",
    "blender": (5, 2, 0),
    "version": (0, 10, 0),
    "location": "View3D",
    "warning": "Early version",
    "category": "Science",
    "License": "MIT",
    "doc_url": "https://blendernc.readthedocs.io/en/docs/",
    "tracker_url": "https://github.com/blendernc/blendernc/issues/",
}


def register():
    """Register BlenderNC with Blender."""
    BNC_register()


def unregister():
    """Unregister BlenderNC from Blender."""
    BNC_unregister()
