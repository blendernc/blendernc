import bpy
import numpy as np

basic_nodes = {
    "BlenderNCNodeImport": {
        "links": {
            "xarray datacube": {
                "BlenderNCNodeCoords": "xarray datacube",
                "BlenderNCNodeVariable": "xarray datacube",
            }
        }
    },
    "BlenderNCNodeCoords": {},
    "BlenderNCNodeVariable": {},
    "BlenderNCNodeGrid": {},
}


def get_node_by_idname(node_tree, bl_idname):
    for node in node_tree.nodes:
        if node.bl_idname == bl_idname:
            return node
    return None


def get_all_nodes_by_idname(bl_idname):
    for node_tree in bpy.data.node_groups:
        for node in node_tree.nodes:
            if node.bl_idname == bl_idname:
                yield node


def create_node(node_tree, node_type, location=(0, 0), return_if_exists=True):
    node_names = [node.name for node in node_tree.nodes if node.bl_idname == node_type]
    if not node_names:
        # Create new node if it doesn't exist.
        node = node_tree.nodes.new(node_type)
    elif return_if_exists:
        # Return existing node if it already exists in the node tree
        node = node_tree.nodes.get(node_names[0])
    else:
        # Create new node
        node = node_tree.nodes.new(node_type)
    node.location = location
    return node


def create_blenderncnodetree(nodetree_name, node_type="BlenderNCNodeTree"):
    if nodetree_name in bpy.data.node_groups:
        nodetree = bpy.data.node_groups.get(nodetree_name)
    else:
        nodetree = bpy.data.node_groups.new(nodetree_name, node_type)
    return nodetree


def create_nodes(node_tree, nodes):
    if node_tree.bl_idname == "GeometryNodeTree":
        nodes["NodeGroupOutput"] = {"links": {}}

    node_types = list(nodes.keys()) if isinstance(nodes, dict) else list(nodes)

    locations = np.vstack(
        (np.linspace(-300, 300, len(node_types)), np.zeros(len(node_types)))
    ).T
    # Move below into decorator

    for i, node_type in enumerate(node_types):
        nodes[node_type]["node"] = create_node(
            node_tree, node_type, location=locations[i]
        )
        nodes[node_type]["name"] = nodes[node_type]["node"].name

    if node_tree.bl_idname == "GeometryNodeTree":
        output_node = nodes["NodeGroupOutput"]["node"]
        if len(output_node.outputs) == 0:
            node_tree.interface.new_socket(
                name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry"
            )

            node_tree.interface.new_socket(
                name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
            )

    create_links(node_tree, nodes)

    return nodes


def create_links(node_tree, nodes):
    for key, value in nodes.items():
        if "links" in value:
            for output_name, input_name in value["links"].items():
                for input_node, socket in input_name.items():
                    create_link(
                        node_tree,
                        nodes[key]["node"],
                        nodes[input_node]["node"],
                        output_name,
                        socket,
                    )


def create_link(node_tree, node_out, node_in, output_name, input_name):
    link_exists = does_link_exists(
        node_tree, node_out, node_in, output_name, input_name
    )
    if not link_exists:
        node_tree.links.new(
            node_out.outputs.get(output_name),
            node_in.inputs.get(input_name),
        )


def does_link_exists(node_tree, node_out, node_in, output_name, input_name):
    exists = False
    for link in node_tree.links:
        if (
            link.from_node == node_out
            and link.to_node == node_in
            and link.from_socket.name == output_name
            and link.to_socket.name == input_name
        ):
            exists = True
            continue
    return exists


def delete_link(node_tree, node_out, node_in, output_name, input_name):
    for link in node_tree.links:
        if link.from_node == node_out and link.to_node == node_in:
            if output_name == "No var" and link.to_socket.name == input_name:
                node_tree.links.remove(link)


def disconnect_links(node_tree, node):
    for link in node_tree.links:
        if link.from_node == node or link.to_node == node:
            node_tree.links.remove(link)
