#!/usr/bin/env python3
import bpy
import sys

# Register the addon and enable it
try:
    bpy.ops.preferences.addon_install(filepath="./blendernc.zip")
except:  # Generic excepts to catch any error
    sys.exit(1)
try:
    bpy.ops.preferences.addon_enable(module="blendernc")
except:  # Generic excepts to catch any error
    sys.exit(2)
