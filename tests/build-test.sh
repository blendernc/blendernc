#!/bin/sh

apt update

apt install libglib2.0-bin --yes

$BLENDERPY -m ensurepip --default-pip

$BLENDERPY -m pip install -r requirements.txt --progress-bar off

# The following line works since the docker container has the "Python.h" file
# required by dependencies of distributed and zarr.
# TODO: Documentation on how to fully take advantages of both of these
#       libraries.
$BLENDERPY -m pip install distributed zarr
$BLENDERPY -m pip install dask[complete] xarray[complete]

$BLENDERPY -m pip install coverage --progress-bar off

$BLENDERPY -m pip install requests --progress-bar off

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

echo $PYTHONPATH

$BLENDERPY -m eccodes selfcheck

$BLENDERPY run_tests.py
test_exit=$?

rm *.png

coverage combine
coverage report

mv ".coverage" ".coverage_${blender_version}"

if [ "$test_exit" -ne 0 ] ; then
  echo "Tests failed!"
  exit 1
fi