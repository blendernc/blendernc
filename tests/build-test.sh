#!/bin/sh

$BLENDERPY -m ensurepip --default-pip

$BLENDERPY -m pip install -r requirements.txt --progress-bar off

$BLENDERPY -m pip install coverage --progress-bar off

# $BLENDERPY -m pip install -e . --progress-bar off

COVERAGE_PROCESS_START="${PWD}"/.coveragerc
export COVERAGE_PROCESS_START=$COVERAGE_PROCESS_START
echo 'import coverage \n coverage.process_startup()'> sitecustomize.py

cd tests

blender -b --python bpy_activate_addon.py

$BLENDERPY run_tests.py
