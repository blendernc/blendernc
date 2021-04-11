#!/usr/bin/env python3
import sys

import bpy

# Register the addon and enable it
try:
    bpy.ops.preferences.addon_install(filepath="./blendernc.zip")
except Exception:  # Generic excepts to catch any error
    sys.exit(1)
try:
    bpy.ops.preferences.addon_enable(module="blendernc")
except Exception:  # Generic excepts to catch any error
    sys.exit(2)
