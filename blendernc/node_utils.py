import bpy

basic_nodes = {
    "BlenderNCNodeImport": {
        "links": {
            "xarray datacube": {
                "BlenderNCNodeResolution": "xarray datacube",
            }
        }
    },
    "BlenderNCNodeResolution": {
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
    "BlenderNCNodeTexture": {},
}

locations = [
    (-400, 0),
    (-200, 0),
    (0, 100),
    (0, -100),
    (200, 100),
    (400, -100),
]


def get_all_nodes_by_idname(bl_idname):
    """Yield every node of a given type across all node groups.

    Parameters
    ----------
    bl_idname : str
        Node type identifier to match.

    Yields
    ------
    bpy.types.Node
        Each matching node in ``bpy.data.node_groups``.
    """
    for node_tree in bpy.data.node_groups:
        for node in node_tree.nodes:
            if node.bl_idname == bl_idname:
                yield node


def create_node(node_tree, node_type, location=(0, 0), return_if_exists=True):
    """Create a node in a tree, or return an existing one of the same type.

    Parameters
    ----------
    node_tree : bpy.types.NodeTree
        Tree in which to create the node.
    node_type : str
        Node type identifier (``bl_idname``).
    location : tuple of float, optional
        Position of the node in the editor, by default ``(0, 0)``.
    return_if_exists : bool, optional
        When ``True`` (default) and a node of this type already exists,
        return it instead of creating another one.

    Returns
    -------
    bpy.types.Node
        The created or existing node, moved to ``location``.
    """
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
    """Return the node group with the given name, creating it if needed.

    Parameters
    ----------
    nodetree_name : str
        Name of the node group.
    node_type : str, optional
        Tree type used when creating, by default ``"BlenderNCNodeTree"``.

    Returns
    -------
    bpy.types.NodeTree
        The existing or newly created node group.
    """
    if nodetree_name in bpy.data.node_groups:
        nodetree = bpy.data.node_groups.get(nodetree_name)
    else:
        nodetree = bpy.data.node_groups.new(nodetree_name, node_type)
    return nodetree


def _row_locations(count, spread=300):
    """Evenly spaced ``(x, 0)`` positions from ``-spread`` to ``spread``."""
    if count < 2:
        return [(0, 0)] * count
    step = 2 * spread / (count - 1)
    return [(-spread + i * step, 0) for i in range(count)]


def _ensure_geometry_interface(node_tree):
    """Give a geometry node tree its ``Geometry`` input and output sockets once."""
    if node_tree.interface.items_tree:
        return
    for in_out in ("INPUT", "OUTPUT"):
        node_tree.interface.new_socket(
            name="Geometry", in_out=in_out, socket_type="NodeSocketGeometry"
        )


def create_nodes(node_tree, nodes, locations=None):
    """Create the nodes of a mapping, or return those that already exist.

    Parameters
    ----------
    node_tree : bpy.types.NodeTree
        Tree in which to create the nodes. A geometry node tree also gets a
        group output node and ``Geometry`` interface sockets.
    nodes : dict
        Mapping of node type identifier to a dict that may hold a ``"links"``
        entry (see :func:`create_links`). Each entry is updated in place with
        the created ``"node"``.
    locations : list of tuple, optional
        One ``(x, y)`` position per node, in mapping order. By default the
        nodes are spread along a row.

    Returns
    -------
    dict
        The same ``nodes`` mapping, populated with node references.
    """
    if node_tree.bl_idname == "GeometryNodeTree":
        nodes.setdefault("NodeGroupOutput", {"links": {}})
        _ensure_geometry_interface(node_tree)

    if locations is None:
        locations = _row_locations(len(nodes))

    for node_type, location in zip(nodes, locations, strict=True):
        nodes[node_type]["node"] = create_node(node_tree, node_type, location)

    return nodes


def create_links(node_tree, nodes):
    """Create the links described in a node mapping.

    Parameters
    ----------
    node_tree : bpy.types.NodeTree
        Tree holding the nodes.
    nodes : dict
        Mapping of node type to a dict with a ``"node"`` reference and an
        optional ``"links"`` entry of the form
        ``{output_socket_name: {target_node_type: input_socket_name}}``.
    """
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
    """Link two sockets by name unless that link already exists.

    Parameters
    ----------
    node_tree : bpy.types.NodeTree
        Tree holding both nodes.
    node_out : bpy.types.Node
        Node providing the output socket.
    node_in : bpy.types.Node
        Node receiving the link on an input socket.
    output_name : str
        Name of the output socket on ``node_out``.
    input_name : str
        Name of the input socket on ``node_in``.
    """
    link_exists = does_link_exists(
        node_tree, node_out, node_in, output_name, input_name
    )
    if not link_exists:
        node_tree.links.new(
            node_out.outputs.get(output_name),
            node_in.inputs.get(input_name),
        )


def does_link_exists(node_tree, node_out, node_in, output_name, input_name):
    """Check whether a link between two named sockets exists.

    Parameters
    ----------
    node_tree : bpy.types.NodeTree
        Tree holding both nodes.
    node_out : bpy.types.Node
        Node providing the output socket.
    node_in : bpy.types.Node
        Node receiving the link.
    output_name : str
        Name of the output socket on ``node_out``.
    input_name : str
        Name of the input socket on ``node_in``.

    Returns
    -------
    bool
        ``True`` if such a link exists.
    """
    for link in node_tree.links:
        if (
            link.from_node == node_out
            and link.to_node == node_in
            and link.from_socket.name == output_name
            and link.to_socket.name == input_name
        ):
            return True
    return False


def delete_link(node_tree, node_out, node_in, output_name, input_name):
    """Remove the link feeding a named input when the output is ``"No var"``.

    Used by the 3D view panel to unlink a coordinate from the grid node when
    the user picks the "No var" entry.

    Parameters
    ----------
    node_tree : bpy.types.NodeTree
        Tree holding both nodes.
    node_out : bpy.types.Node
        Node on the output side of the link.
    node_in : bpy.types.Node
        Node on the input side of the link.
    output_name : str
        Selected output name; only ``"No var"`` triggers removal.
    input_name : str
        Name of the input socket on ``node_in`` to disconnect.
    """
    for link in node_tree.links:
        if link.from_node == node_out and link.to_node == node_in:
            if output_name == "No var" and link.to_socket.name == input_name:
                node_tree.links.remove(link)


def disconnect_links(node_tree, node):
    """Remove every link attached to a node.

    Parameters
    ----------
    node_tree : bpy.types.NodeTree
        Tree holding the node.
    node : bpy.types.Node
        Node whose incoming and outgoing links are removed.
    """
    for link in node_tree.links:
        if link.from_node == node or link.to_node == node:
            node_tree.links.remove(link)
