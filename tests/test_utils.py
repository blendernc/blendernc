import contextlib
import os
import sys


@contextlib.contextmanager
def suppress_stdout():
    with open(os.devnull, "w") as devnull:
        old_stdout = sys.stdout
        sys.stdout = devnull
        try:
            yield
        finally:
            sys.stdout = old_stdout


# Use the context manager to hide logs for specific operations
# with suppress_stdout():
#     # Call your bpy.rna or bpy.ops functions here
#     print("This log (and Blender C-logs) will be hidden")
