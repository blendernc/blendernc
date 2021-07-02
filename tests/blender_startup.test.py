#!/usr/bin/env python
import unittest
from subprocess import PIPE, Popen

import bpy

blenderExecutable = "blender"


class Test_blender_startup(unittest.TestCase):
    def is_stdout_expected(self, stdout):
        true_list = []
        lines = stdout.decode("utf-8")
        for line in lines.split("\n"):
            if "Registering to Change Defaults" in line:
                true_list.append(True)
            elif "Unregistering to Change Defaults" in line:
                true_list.append(True)
            elif "Blender quit" in line:
                true_list.append(True)
        return true_list

    def test_preference(self):
        cmd = [
            blenderExecutable,
            "--addons",
            "blendernc",
            "-E",
            "CYCLES",
            "-b",
            "--python-use-system-env",
            "--python",
            "",
        ]

        p = Popen(cmd, stdout=PIPE)
        stdout, _ = p.communicate()
        print(stdout)
        expected_lines_stdout = len(self.is_stdout_expected(stdout))
        # Blender < 2.91 doesn't unregister classes when closing.
        if bpy.app.version < (2, 91, 0):
            self.assertEqual(2, expected_lines_stdout)
        else:
            self.assertEqual(3, expected_lines_stdout)
        self.assertEqual(None, _)


# we have to manually invoke the test runner here, as we cannot use the CLI
suite = unittest.defaultTestLoader.loadTestsFromTestCase(
    Test_blender_startup,
)
unittest.TextTestRunner().run(suite)
