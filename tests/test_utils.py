#!/usr/bin/env python
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


def refresh_state(func):
    def wrapper(*args, **kwargs):
        func(*args, **kwargs)
        node_groups = bpy.data.node_groups
        if is_blendernc_in_nodetree(node_groups):
            bpy.context.scene.nc_cache.pop("BlenderNC")
        print("Purge")

    return wrapper
