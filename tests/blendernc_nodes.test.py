import os
import sys
import unittest

import bpy


def is_blendernc_in_nodetree(node_groups):
    node_groups_keys = node_groups.keys()

    for node_groups_name in node_groups_keys:
        if "BlenderNC" in node_groups_name:
            return True
    return False


def create_nodes(node_list):
    node_tree = bpy.data.node_groups["BlenderNC"]
    node_tree.use_fake_user = True
    list_length = len(node_list)
    node_dist = [ii - list_length / 2 for ii in range(list_length)]
    node_names = []
    for inode in range(list_length):
        node = node_tree.nodes.new(node_list[inode])
        node.location = (node_dist[inode] * 200, 0)
        node_names.append(node.name)
    return node_names


def join_nodes(node_tree, existing_nodes, props):
    count = 1
    for node in existing_nodes:
        for pro, item in props[node.name].items():
            setattr(node, pro, item)
        if count < len(existing_nodes):
            node_tree.links.new(existing_nodes[count].inputs[0], node.outputs[0])
            print("Link {0} -> {1}".format(node.name, existing_nodes[count].name))
        count += 1


def build_dict_blendernc_prop(existing_nodes_list):
    prop_dict = {}
    for node in existing_nodes_list:
        node_dir = dir(node)
        blendernc_prop_list = []
        for _dir in node_dir:
            if "blendernc" in _dir:
                blendernc_prop_list.append(_dir)

        if node.name == "netCDF input":
            blendernc_prop_list.remove("blendernc_file")
            blendernc_prop_list.remove("blendernc_dict")
            blendernc_prop_list.remove("blendernc_dataset_identifier")
        elif node.name != "netCDF Path":
            blendernc_prop_list.remove("blendernc_dataset_identifier")
            blendernc_prop_list.remove("blendernc_dict")

        prop_dict[node.name] = {
            prop: getattr(node, prop) for prop in blendernc_prop_list
        }
    return prop_dict


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


def refresh_state(func):
    def wrapper(*args, **kwargs):
        func(*args, **kwargs)
        node_groups = bpy.data.node_groups
        if is_blendernc_in_nodetree(node_groups):
            bpy.context.scene.nc_cache.pop("BlenderNC")
        print("Purge")

    return wrapper


@refresh_state
def render_image(file, var, node_list=[], node_args=None):
    node_groups = bpy.data.node_groups
    if is_blendernc_in_nodetree(node_groups):
        node_groups.remove(node_groups["BlenderNC"])

    bpy.data.node_groups.new("BlenderNC", "BlenderNC")

    # Create nodes
    nodes = ["netCDFPath", "netCDFNode", "netCDFResolution", "netCDFOutput"]
    for node in node_list[::-1]:
        nodes.insert(3, node)

    node_names = create_nodes(nodes)

    print("Testing nodes:")
    print(*nodes)

    node_tree = bpy.data.node_groups["BlenderNC"]
    existing_nodes = [node_tree.nodes[node] for node in node_names]
    # Now let's change properties.
    props = build_dict_blendernc_prop(existing_nodes)

    props["netCDF Path"]["blendernc_file"] = file
    props["netCDF input"]["blendernc_netcdf_vars"] = var
    props["Resolution"]["bendernc_resolution"] = 80

    if node_args:
        for key, args in node_args.items():
            props[key] = args

    join_nodes(node_tree, existing_nodes, props)

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

    directory = bpy.path.abspath("//")
    name_dataset = os.path.basename(file).split(".")
    image_path = f"{directory}" + "{0}_{1}_image_{2}_{3}.png".format(
        name_dataset[0], var, format[-1], "_".join(node_list)
    )
    existing_nodes[-1].image.filepath_raw = image_path
    existing_nodes[-1].image.file_format = "PNG"
    existing_nodes[-1].image.save()


class Test_use_nodes(unittest.TestCase):
    def test_math(self):
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        var = "adt"
        format = os.path.basename(file).split(".")
        nodes = ["netCDFmath"]
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
        nodes = ["netCDFtime", "netCDFmath"]
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
        nodes = ["netCDFmath", "netCDFtime"]
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
        nodes = ["netCDFRange"]
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
        nodes = ["netCDFRange", "netCDFmath"]
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
        nodes = ["netCDFrotatelon"]
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
        nodes = ["netCDFrotatelon", "netCDFRange"]
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
        nodes = ["netCDFtime"]
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
        nodes = ["netCDFdims"]
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
        nodes = ["netCDFsort"]
        dims_args = {"Sortby Dimension": {"blendernc_dims": "time"}}
        render_image(file, var, nodes, node_args=dims_args)
        file_exist = os.path.isfile(
            "./{0}_{1}_image_{2}_{3}.png".format(
                format[0], var, format[-1], "_".join(nodes)
            )
        )
        self.assertTrue(file_exist)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_use_nodes)
unittest.TextTestRunner().run(suite)
