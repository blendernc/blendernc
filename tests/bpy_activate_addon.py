#!/usr/bin/env python3
import os
import sys
from pathlib import Path

import bpy

python_path = Path(sys.executable)
blender_path = Path(bpy.app.binary_path)
blender_directory = blender_path.parent

version = bpy.app.version
user_addon_directory = Path(bpy.utils.user_resource("SCRIPTS", path="addons"))

directory = os.path.abspath("../")
module_name = os.path.basename(directory)

link_path = os.path.join(user_addon_directory, module_name)

if os.path.exists(user_addon_directory):
    if os.path.exists(link_path):
        os.remove(link_path)
else:
    os.makedirs(user_addon_directory)

print("Linking {0} to {1}".format(directory, link_path))

if sys.platform == "win32":
    import _winapi

    _winapi.CreateJunction(str(directory), str(link_path))
else:
    os.symlink(str(directory), str(link_path), target_is_directory=True)

sys.path.append(str(user_addon_directory))

# try:
#     bpy.ops.preferences.addon_refresh()
#     bpy.ops.preferences.addon_enable(module="blendernc")
# except Exception:  # Generic excepts to catch any error
#     sys.exit(1)
