import glob
import subprocess
import sys

# This script is based on:
# https://anzui.dev/blog/2015/05-21/automatic-blender-addon-testing-travisci

blenderExecutable = "blender"

# allow override of blender executable (important for CI!)
if len(sys.argv) > 1:
    blenderExecutable = sys.argv[1]

# iterate over each *.test.blend file in the "tests" directory
# and open up blender with the .test.blend
# file and the corresponding .test.py python script

errors = {}

for file in glob.glob("./*.test.py"):
    # change 'blendernc' to match your addon
    print("Running file: {0}".format(file))
    # Currently EVEE is not supported without a display.
    # TODO: Try to fake display (See link below)
    # https://github.com/nytimes/rd-blender-docker/issues/3#issuecomment-620199501
    # blender --background --addons "blendernc" -E CYCLES --python "test_default.py"
    proc = subprocess.run(
        [
            blenderExecutable,
            "--addons",
            "blendernc",
            "-E",
            "CYCLES",
            "-b",
            "--python-use-system-env",
            "--python",
            file,
        ],
    )

    if proc.returncode != 0:
        errors[proc.args[-1]] = proc.returncode

# Catch errors
if errors:
    message = ""
    for keys, code in errors.items():
        message += "Test file: {0} failed (Code={1}).".format(keys, code)
    raise RuntimeError(message)
