import os
import sys
import unittest

import bpy


def capture_render_log(func):
    def wrapper(*args, **kwargs):
        logfile = "blender_render.log"
        open(logfile, "a").close()
        old = os.dup(1)
        sys.stdout.flush()
        os.close(1)
        os.open(logfile, os.O_WRONLY)
        func(*args, **kwargs)
        os.close(1)
        os.dup(old)

    return wrapper


@capture_render_log
def render_image(file, var, res):
    bpy.context.scene.blendernc_file = file
    bpy.context.scene.blendernc_netcdf_vars = var
    bpy.context.scene.blendernc_resolution = res

    # Delete cube
    object_keys = bpy.data.objects.keys()

    if "Cube" in object_keys:
        bpy.data.objects["Cube"].select_set(True)  # Blender 2.8x
        bpy.ops.object.delete()

    if "Plane" not in object_keys:
        bpy.ops.mesh.primitive_plane_add()

    plane = bpy.data.objects["Plane"]
    plane.select_set(True)

    node_tree = bpy.data.node_groups["BlenderNC"]
    out = node_tree.nodes["Output"]

    image_size_x = out.image.pixels.data.size[0]
    image_size_y = out.image.pixels.data.size[1]

    if image_size_x < image_size_x:
        ratio = image_size_y / image_size_x
    else:
        ratio = image_size_x / image_size_y

    plane.scale[0] = ratio

    bpy.ops.blendernc.apply_material()

    blender_render_image(file, var)
    # Test for change in res
    bpy.context.scene.blendernc_resolution = 10


@capture_render_log
def blender_render_image(file, var):
    scene = bpy.context.scene
    render = scene.render
    directory = bpy.path.abspath("//")

    format = file.split(".")[-1]
    render.filepath = f"{directory}" + "{0}_image_{1}.png".format(var, format)
    bpy.ops.render.render(write_still=True)

    render.filepath = directory


class Test_format_import(unittest.TestCase):
    def test_import_UI(self):
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        var = "adt"
        res = 100
        format = file.split(".")[-1]
        render_image(file, var, res)
        file_exist = os.path.isfile("./UI_{0}_image_{1}.png".format(var, format))
        self.assertTrue(file_exist)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_format_import)
unittest.TextTestRunner().run(suite)
