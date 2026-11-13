#!/bin/sh
# Combine the coverage data uploaded by every Blender job of the test workflow.
# Runs inside the CI Docker image so the recorded /blendernc paths resolve.

python -m pip install coverage --progress-bar off

cd ./tests/ || exit 1
# download-artifact puts each artifact in ./coverage_<blender>/; flatten them.
mv ./coverage_*/.coverage* .
# Combine, report and write coverage.xml for Codecov.
python -m coverage combine .coverage_Blender*
python -m coverage report
python -m coverage xml
