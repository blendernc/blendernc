#!/bin/sh

apt install libglib2.0-bin --yes

$BLENDERPY -m ensurepip --default-pip

$BLENDERPY -m pip install -r requirements.txt --progress-bar off

$BLENDERPY -m pip install coverage --progress-bar off

$BLENDERPY -m pip install -e . --progress-bar off

blender_version=$(blender --version | head -n 1)
echo ${blender_version}

COVERAGE_PROCESS_START=${PWD}"/.coveragerc"
export COVERAGE_PROCESS_START=$COVERAGE_PROCESS_START
export PYTHONPATH=$PYTHONPATH:${PWD}

cd tests

echo -e "import coverage \n\ncov=coverage.process_startup()\n"> sitecustomize.py
echo -e "print('Initiate coverage')" >> sitecustomize.py
echo -e "print(cov)" >> sitecustomize.py

export PYTHONPATH=$PYTHONPATH:${PWD}

$BLENDERPY run_tests.py

rm *.png

coverage combine
coverage report

mv ".coverage" ".coverage_${blender_version}"