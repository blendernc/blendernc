#!/bin/sh

$BLENDERPY -m pip install coverage --progress-bar off

# Navegate to test
cd ./tests/
# Move all coverage files from within default download-artifact structure
mv ./coverage_*/* .
# Combine, create coverage.xml and report coverage.
coverage combine .coverage_Blender*
coverage report
coverage xml
