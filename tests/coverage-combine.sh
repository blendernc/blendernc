#!/bin/sh

$BLENDERPY -m pip install coverage --progress-bar off

cd ./tests/
ls -la .
coverage combine .coverage_*
coverage report
coverage xml
