#!/bin/sh

$BLENDERPY -m ensurepip --default-pip

$BLENDERPY -m pip install -r requirements.txt
blender --background --python ./bpy_activate_addon.py