#!/bin/sh

$BLENDERPY -m ensurepip --default-pip

$BLENDERPY -m pip install -r requirements.txt

$BLENDERPY -m pip install -e .

blender --background --python ./bpy_activate_addon.py