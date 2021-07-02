#!/bin/sh

$BLENDERPY -m pip install coverage --progress-bar off

cd ./tests/
coverage combine .coverage_Blender*
coverage report
coverage xml
