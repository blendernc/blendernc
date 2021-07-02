#!/bin/sh

$BLENDERPY -m pip install coverage --progress-bar off

cd ./tests/
coverage combine .coverage_*
coverage report
coverage xml
