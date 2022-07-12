import os
import sys
import unittest

import bpy

import tests.test_utils as tutils


@tutils.refresh_state
def render_image(file, var, node_list=[], node_args=None):
    node_groups = bpy.data.node_groups
    if tutils.is_blendernc_in_nodetree(node_groups):
        node_groups.remove(node_groups["BlenderNC"])

    bpy.data.node_groups.new("BlenderNC", "BlenderNC")

    # Create nodes
    nodes = ["datacubePath", "datacubeNode", "datacubeResolution", "datacubeOutput"]
    for node in node_list[::-1]:
        nodes.insert(3, node)

    node_names = tutils.create_nodes(nodes)

    print("Testing nodes:")
    print(*nodes)

    node_tree = bpy.data.node_groups["BlenderNC"]
    existing_nodes = [node_tree.nodes[node] for node in node_names]
    # Now let's change properties.
    props = tutils.build_dict_blendernc_prop(existing_nodes)

    props["datacube Path"]["blendernc_file"] = file
    props["datacube Input"]["blendernc_datacube_vars"] = var
    props["Resolution"]["bendernc_resolution"] = 80

    if node_args:
        for key, args in node_args.items():
            props[key] = args

    tutils.join_nodes(node_tree, existing_nodes, props)

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
    existing_nodes[-1].image = bpy.data.images.get("BlenderNC_default")

    # Delete cube
    object_keys = bpy.data.objects.keys()

    if "Cube" in object_keys:
        bpy.data.objects["Cube"].select_set(True)  # Blender 2.8x
        bpy.ops.object.delete()

    if "Plane" not in object_keys:
        bpy.ops.mesh.primitive_plane_add()

    plane = bpy.data.objects["Plane"]
    plane.select_set(True)

    image_size_x = existing_nodes[-1].image.pixels.data.size[0]
    image_size_y = existing_nodes[-1].image.pixels.data.size[1]

    if image_size_x < image_size_x:
        ratio = image_size_y / image_size_x
    else:
        ratio = image_size_x / image_size_y

    plane.scale[0] = ratio

    bpy.ops.blendernc.apply_material()

    directory = os.path.abspath("//")
    name_dataset = os.path.basename(file).split(".")
    image_path = f"{directory}" + "{0}_{1}_image_{2}_{3}.png".format(
        name_dataset[0], var, name_dataset[-1], "_".join(node_list)
    )
    existing_nodes[-1].image.filepath_raw = image_path
    existing_nodes[-1].image.file_format = "PNG"
    existing_nodes[-1].image.save()


class Test_use_nodes(unittest.TestCase):
    def test_math(self):
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        var = "adt"
        format = os.path.basename(file).split(".")
        nodes = ["datacubeMath"]
        render_image(file, var, nodes)
        file_exist = os.path.isfile(
            "./{0}_{1}_image_{2}_{3}.png".format(
                format[0], var, format[-1], "_".join(nodes)
            )
        )
        self.assertTrue(file_exist)

    def test_math_time(self):
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        var = "adt"
        format = os.path.basename(file).split(".")
        nodes = ["datacubeTime", "datacubeMath"]
        render_image(file, var, nodes)
        file_exist = os.path.isfile(
            "./{0}_{1}_image_{2}_{3}.png".format(
                format[0], var, format[-1], "_".join(nodes)
            )
        )
        self.assertTrue(file_exist)

    def test_math_time_flipped(self):
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        var = "adt"
        format = os.path.basename(file).split(".")
        nodes = ["datacubeMath", "datacubeTime"]
        render_image(file, var, nodes)
        file_exist = os.path.isfile(
            "./{0}_{1}_image_{2}_{3}.png".format(
                format[0], var, format[-1], "_".join(nodes)
            )
        )
        self.assertTrue(file_exist)

    def test_range(self):
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        var = "adt"
        format = os.path.basename(file).split(".")
        nodes = ["datacubeRange"]
        render_image(file, var, nodes)
        file_exist = os.path.isfile(
            "./{0}_{1}_image_{2}_{3}.png".format(
                format[0], var, format[-1], "_".join(nodes)
            )
        )
        self.assertTrue(file_exist)

    def test_range_math(self):
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        var = "adt"
        format = os.path.basename(file).split(".")
        nodes = ["datacubeRange", "datacubeMath"]
        render_image(file, var, nodes)
        file_exist = os.path.isfile(
            "./{0}_{1}_image_{2}_{3}.png".format(
                format[0], var, format[-1], "_".join(nodes)
            )
        )
        self.assertTrue(file_exist)

    def test_rotatelon(self):
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        var = "adt"
        format = os.path.basename(file).split(".")
        nodes = ["datacubeRotatelon"]
        render_image(file, var, nodes)
        file_exist = os.path.isfile(
            "./{0}_{1}_image_{2}_{3}.png".format(
                format[0], var, format[-1], "_".join(nodes)
            )
        )
        self.assertTrue(file_exist)

    def test_rotatelon_range(self):
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        var = "adt"
        format = os.path.basename(file).split(".")
        nodes = ["datacubeRotatelon", "datacubeRange"]
        render_image(file, var, nodes)
        file_exist = os.path.isfile(
            "./{0}_{1}_image_{2}_{3}.png".format(
                format[0], var, format[-1], "_".join(nodes)
            )
        )
        self.assertTrue(file_exist)

    def test_time(self):
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        var = "adt"
        format = os.path.basename(file).split(".")
        nodes = ["datacubeTime"]
        render_image(file, var, nodes)
        file_exist = os.path.isfile(
            "./{0}_{1}_image_{2}_{3}.png".format(
                format[0], var, format[-1], "_".join(nodes)
            )
        )
        self.assertTrue(file_exist)

    def test_dropdims(self):
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        var = "adt"
        format = os.path.basename(file).split(".")
        nodes = ["datacubeDims"]
        # blendernc_dims
        dims_args = {"Drop Dimension": {"blendernc_dims": "time"}}
        render_image(file, var, nodes, node_args=dims_args)
        file_exist = os.path.isfile(
            "./{0}_{1}_image_{2}_{3}.png".format(
                format[0], var, format[-1], "_".join(nodes)
            )
        )
        self.assertTrue(file_exist)

    def test_sortby(self):
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        var = "adt"
        format = os.path.basename(file).split(".")
        nodes = ["datacubeSort"]
        dims_args = {"Sortby Dimension": {"blendernc_dims": "time"}}
        render_image(file, var, nodes, node_args=dims_args)
        file_exist = os.path.isfile(
            "./{0}_{1}_image_{2}_{3}.png".format(
                format[0], var, format[-1], "_".join(nodes)
            )
        )
        self.assertTrue(file_exist)

    def test_axis(self):
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        var = "adt"
        format = os.path.basename(file).split(".")
        nodes = ["datacubeAxis"]
        dims_args = {"Select Axis": {"axes": "time"}}
        render_image(file, var, nodes, node_args=dims_args)
        file_exist = os.path.isfile(
            "./{0}_{1}_image_{2}_{3}.png".format(
                format[0], var, format[-1], "_".join(nodes)
            )
        )
        self.assertTrue(file_exist)

    def test_unlink_copy_node(self):
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        var = "adt"
        nodes = ["datacubeRange"]
        dims_args = {
            "datacube Range": {"blendernc_dataset_min": -1, "blendernc_dataset_max": 1}
        }
        render_image(file, var, nodes, node_args=dims_args)
        node_tree = bpy.data.node_groups["BlenderNC"]
        node = node_tree.nodes.get("datacube Input")
        links = node.outputs[0].links
        for link in links:
            link.from_socket.unlink(link)
        output = node_tree.nodes.get("Output")
        output.copy(output)
        self.assertFalse(output.blendernc_dataset_identifier)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_use_nodes)
test = unittest.TextTestRunner().run(suite)

ret = not test.wasSuccessful()
sys.exit(ret)
