import sys
import unittest

import addon_utils
import bpy
import requests

# import tests.test_utils as tutils


zip_file_url = (
    "https://github.com/blendernc/blendernc-zip-install/raw/master/blendernc.zip"
)


def download_url(url, save_path, chunk_size=128):
    r = requests.get(url, stream=True)
    with open(save_path, "wb") as fd:
        for chunk in r.iter_content(chunk_size=chunk_size):
            fd.write(chunk)


download_url(zip_file_url, "blendernc.zip")


class Test_install(unittest.TestCase):
    def test_install_zip(self):
        bpy.ops.preferences.addon_disable(module="blendernc")
        bpy.ops.preferences.addon_remove(module="blendernc")
        bpy.ops.preferences.addon_install(filepath="./blendernc.zip", overwrite=True)
        bpy.ops.preferences.addon_enable(module="blendernc")
        addon_modules = []
        for mod in addon_utils.modules():
            addon_modules.append(mod.bl_info.get("name"))
        self.assertTrue("BlenderNC" in addon_modules)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_install)
test = unittest.TextTestRunner().run(suite)

ret = not test.wasSuccessful()
sys.exit(ret)
