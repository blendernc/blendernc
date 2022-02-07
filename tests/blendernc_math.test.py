import os
import sys
import unittest

import bpy
import numpy as np

import tests.test_utils as tutils
from blendernc.nodes.math.BlenderNC_NT_math import ops


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
    image_path = f"{directory}" + "{0}_{1}_image_{2}_{3}_{4}.png".format(
        name_dataset[0],
        var,
        name_dataset[-1],
        "_".join(node_list),
        node_args["Math"]["blendernc_operation"],
    )
    existing_nodes[-1].image.filepath_raw = image_path
    existing_nodes[-1].image.file_format = "PNG"
    existing_nodes[-1].image.save()
    return existing_nodes


class Test_use_nodes(unittest.TestCase):
    def test_math_switch_ops(self):
        bpy.ops.wm.read_homefile()
        file_exist = True
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        var = "adt"
        format = os.path.basename(file).split(".")
        nodes = ["datacubeMath"]
        for key in ops.keys():
            print("Testing", key)
            dims_args = {"Math": {"blendernc_operation": key, "update_range": False}}
            render_image(file, var, nodes, node_args=dims_args)
            filename = "./{0}_{1}_image_{2}_{3}_{4}.png".format(
                format[0], var, format[-1], "_".join(nodes), key
            )
            if not os.path.isfile(filename):
                file_exist = False
                break
        self.assertTrue(file_exist)

    def test_dataset_math(self):
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        var = "adt"
        nodes = ["datacubeMath"]
        dims_args = {"Math": {"blendernc_operation": "Add", "update_range": True}}
        bl_nodes = render_image(file, var, nodes, node_args=dims_args)
        math_node = [node for node in bl_nodes if node.bl_idname == "datacubeMath"]
        node_tree = math_node[0].id_data
        data_node = math_node[0].inputs[0].links[0].from_node
        parent_identifier = data_node.blendernc_dataset_identifier
        dataset_before = data_node.blendernc_dict[parent_identifier][
            "Dataset"
        ].adt.values
        node_tree.links.new(math_node[0].inputs[1], data_node.outputs[0])
        node_identifier = math_node[0].blendernc_dataset_identifier
        dataset = math_node[0].blendernc_dict[node_identifier]["Dataset"].adt.values
        mean_value = np.nanmean(dataset // dataset_before)
        # Unlink nodes
        math_node[0].inputs[1].unlink(math_node[0].inputs[1].links[0])
        self.assertTrue(mean_value == 2.0)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_use_nodes)
test = unittest.TextTestRunner().run(suite)

ret = not test.wasSuccessful()
sys.exit(ret)
