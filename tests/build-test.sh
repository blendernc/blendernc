#!/bin/sh
apt-get update --fix-missing

apt-get install libglib2.0-bin --yes

python -m ensurepip --default-pip

python -m pip install --upgrade pip

python -m pip install coverage --progress-bar off

COVERAGE_PROCESS_START=${PWD}"/.coveragerc"
export COVERAGE_PROCESS_START=$COVERAGE_PROCESS_START
export PYTHONPATH=$PYTHONPATH:${PWD}

cd tests

echo -e "import coverage \n\ncov=coverage.process_startup()\n"> sitecustomize.py
echo -e "print('Initiate coverage')" >> sitecustomize.py
echo -e "print(cov)" >> sitecustomize.py

export PYTHONPATH=$PYTHONPATH:${PWD}

echo $PYTHONPATH

# Run tests before installing libraries:
python run_tests.py "blender" "test_nolib"
test_nolib_exit=$?

rm ./sitecustomize.py

cd ..

python -m pip install -r requirements.txt --progress-bar off

blender_version=$(blender --version | head -n 1)
echo ${blender_version}

cd tests

echo $PYTHONPATH

python -m cfgrib selfcheck

# Create again the sitecustomize file.
echo -e "import coverage \n\ncov=coverage.process_startup()\n"> sitecustomize.py
echo -e "print('Initiate coverage')" >> sitecustomize.py
echo -e "print(cov)" >> sitecustomize.py

python run_tests.py
test_exit=$?

rm *.png

python -m coverage combine
python -m coverage report

mv ".coverage" ".coverage_${blender_version}"

if [[ "$test_exit" -ne 0 ]] && [[ "$test_nolib_exit" -ne 0 ]] ; then
  echo "Tests failed!"
  exit 1
fi