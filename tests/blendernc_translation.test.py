import os
import sys
import unittest

import bpy

from blendernc.translations import translate


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
def render_image(file, var):
    node_groups = bpy.data.node_groups
    node_groups_keys = node_groups.keys()

    for node_groups_name in node_groups_keys:
        if "BlenderNC" in node_groups_name:
            node_groups.remove(node_groups[node_groups_name])

    bpy.data.node_groups.new("BlenderNC", "BlenderNC")

    node_tree = bpy.data.node_groups["BlenderNC"]
    node_tree.use_fake_user = True

    # Create nodes
    path = node_tree.nodes.new("datacubePath")
    path.location = (-350, 0)
    inp = node_tree.nodes.new("datacubeNode")
    inp.location = (-125, 0)
    res = node_tree.nodes.new("datacubeResolution")
    res.location = (125, 0)
    out = node_tree.nodes.new("datacubeOutput")
    out.location = (350, 0)

    # Select variable
    path.blendernc_file = file
    # Connect path node to datacube node
    node_tree.links.new(inp.inputs[0], path.outputs[0])
    # Select variable
    inp.blendernc_datacube_vars = var
    # Change resolution
    res.blendernc_resolution = 100

    # Connect links
    node_tree.links.new(res.inputs[0], inp.outputs[0])
    node_tree.links.new(out.inputs[0], res.outputs[0])

    # Create new image
    bpy.ops.image.new(
        name="BlenderNC_default",
        width=1024,
        height=1024,
        color=(0.0, 0.0, 0.0, 1.0),
        alpha=True,
        generated_type="BLANK",
        float=True,
    )

    # Assign new image to node
    out.image = bpy.data.images.get("BlenderNC_default")

    # Delete cube
    object_keys = bpy.data.objects.keys()

    if "Cube" in object_keys:
        bpy.data.objects["Cube"].select_set(True)  # Blender 2.8x
        bpy.ops.object.delete()

    if translate("Plane") not in object_keys:
        bpy.ops.mesh.primitive_plane_add()

    plane = bpy.data.objects[translate("Plane")]
    plane.select_set(True)

    image_size_x = out.image.pixels.data.size[0]
    image_size_y = out.image.pixels.data.size[1]

    if image_size_x < image_size_x:
        ratio = image_size_y / image_size_x
    else:
        ratio = image_size_x / image_size_y

    plane.scale[0] = ratio

    bpy.ops.blendernc.apply_material()

    scene = bpy.context.scene
    render = scene.render
    directory = bpy.path.abspath("//")

    format = file.split(".")[-1]
    render.filepath = f"{directory}" + "{0}_image_{1}.png".format(var, format)
    bpy.ops.render.render(write_still=True)

    render.filepath = directory


class Test_translation(unittest.TestCase):
    def test_language_chinese(self):
        bpy.context.preferences.view.language = "zh_CN"
        bpy.ops.wm.read_homefile()
        bpy.context.scene.render.engine = "CYCLES"
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        var = "adt"
        format = file.split(".")[-1]
        render_image(file, var)
        file_exist = os.path.isfile("./{0}_image_{1}.png".format(var, format))
        self.assertTrue(file_exist)

    def test_language_spanish(self):
        bpy.context.preferences.view.language = "es"
        bpy.ops.wm.read_homefile()
        bpy.context.scene.render.engine = "CYCLES"
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        var = "adt"
        format = file.split(".")[-1]
        render_image(file, var)
        file_exist = os.path.isfile("./{0}_image_{1}.png".format(var, format))
        self.assertTrue(file_exist)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_translation)
test = unittest.TextTestRunner().run(suite)

ret = not test.wasSuccessful()
sys.exit(ret)
