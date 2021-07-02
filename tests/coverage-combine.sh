#!/bin/sh

$BLENDERPY -m pip install coverage --progress-bar off

ls .
cd ./tests/
ls .
coverage combine .coverage_*
coverage report
coverage xml
