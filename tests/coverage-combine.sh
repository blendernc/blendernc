#!/bin/sh

python -m pip install coverage --progress-bar off

# Navegate to test
cd ./tests/
# Move all coverage files from within default download-artifact structure
mv ./coverage_*/.coverage* .
# Combine, create coverage.xml and report coverage.
python -m coverage combine .coverage_Blender*
python -m coverage report
python -m coverage xml
