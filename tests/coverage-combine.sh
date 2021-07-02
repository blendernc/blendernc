#!/bin/sh

$BLENDERPY -m pip install coverage --progress-bar off

ls -la .
# Navegate to test
cd ./tests/
ls -la .
# Move all coverage files from within default download-artifact structure
ls -la ./coverage_*
mv ./coverage_*/* .
# Combine, create coverage.xml and report coverage.
coverage combine .coverage_Blender*
coverage report
coverage xml
