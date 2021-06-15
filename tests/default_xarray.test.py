import os
import unittest

import bpy


def render_image():
    node_groups = bpy.data.node_groups
    node_groups_keys = node_groups.keys()

    for node_groups_name in node_groups_keys:
        if "BlenderNC" in node_groups_name:
            node_groups.remove(node_groups[node_groups_name])

    bpy.data.node_groups.new("BlenderNC", "BlenderNC")

    node_tree = bpy.data.node_groups["BlenderNC"]
    node_tree.use_fake_user = True

    # Create nodes
    inp = node_tree.nodes.new("Datacube_tutorial")
    inp.location = (-300, 0)
    res = node_tree.nodes.new("netCDFResolution")
    res.location = (0, 0)
    out = node_tree.nodes.new("netCDFOutput")
    out.location = (300, 0)

    # Select variable
    inp.blendernc_xarray_datacube = "air_temperature"
    inp.blendernc_netcdf_vars = "air"

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

    if "Plane" not in object_keys:
        bpy.ops.mesh.primitive_plane_add()

    plane = bpy.data.objects["Plane"]
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

    render.filepath = f"{directory}" + "test_image.png"
    bpy.ops.render.render(write_still=True)

    render.filepath = directory


class Test_simple_render(unittest.TestCase):
    def test_render_tutorial_data(self):
        render_image()
        file_exist = os.path.isfile("./test_image.png")
        self.assertTrue(file_exist)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_simple_render)
unittest.TextTestRunner().run(suite)
