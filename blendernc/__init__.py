#!/usr/bin/env python3

##############################################################################
# .                                 IMPORTANT                                #
##############################################################################
#     This file is only used for unit testing and should not be used in      #
# production. It is not part of the BlenderNC extension and is not intended  #
#   to be used by end users. It is only used for testing purposes and may be #
#                  removed in future versions of BlenderNC.                  #
##############################################################################
##############################################################################

__version__ = "0.12.0"

bl_info = {
    "name": "BlenderNC",
    "author": "Oriol Tintó Prims & Josué Martínez-Moreno",
    "description": "Blender Add-On to visualize geo-scientific data",
    "blender": (5, 2, 0),
    "version": (0, 12, 0),
    "location": "View3D",
    "warning": "Early version",
    "category": "Science",
    "License": "MIT",
    "doc_url": "https://blendernc.readthedocs.io/en/docs/",
    "tracker_url": "https://github.com/blendernc/blendernc/issues/",
}


# The add-on is imported when registered, not with the package, so that
# ``blendernc.core`` can be imported, and unit-tested, without Blender.


def register():
    """Register BlenderNC with Blender."""
    from .blendernc import register as bnc_register

    bnc_register()


def unregister():
    """Unregister BlenderNC from Blender."""
    from .blendernc import unregister as bnc_unregister

    bnc_unregister()
