#!/bin/sh

$BLENDERPY -m ensurepip --default-pip

$BLENDERPY -m pip install -r requirements.txt --progress-bar off

$BLENDERPY -m pip install -e . --progress-bar off

blender --background --python ./bpy_activate_addon.py