"""Colormap shader node and its menus, for materials built by BlenderNC.

Port of ``nodes/cmaps/ShaderNodeValToCMAP.py`` from the ``master`` branch, updated for
Blender 5.2: each Colormap node owns its node group (Group Input, Color Ramp,
Group Output) instead of sharing one group with suffixed node names.
"""

import bpy

from .node_utils import create_links, create_nodes
from .shader_utils import (
    apply_colormap,
    available_colormaps,
    decode_colormap,
    default_colormap,
    encode_colormap,
    get_colormap,
    set_fill_color,
)

# Name given to every Colormap node's group; Blender adds ".001" and so on.
COLORMAP_GROUP = ".Colormap"

# Columns of the colormap menu hold at most this many names.
MENU_COLUMN_LENGTH = 16

_GROUP_NODES = {
    "NodeGroupInput": {"links": {"Factor": {"ShaderNodeValToRGB": "Factor"}}},
    "ShaderNodeValToRGB": {"links": {"Color": {"NodeGroupOutput": "Color"}}},
    "NodeGroupOutput": {},
}


def _new_colormap_group():
    """Create the node group used inside one Colormap node."""
    group = bpy.data.node_groups.new(COLORMAP_GROUP, "ShaderNodeTree")
    group.interface.new_socket("Factor", in_out="INPUT", socket_type="NodeSocketFloat")
    group.interface.new_socket("Color", in_out="OUTPUT", socket_type="NodeSocketColor")
    nodes = create_nodes(group, _GROUP_NODES, [(-300, 0), (0, 0), (300, 0)])
    create_links(group, nodes)
    return group


def _shader_trees():
    """Every shader node tree: material trees and shader node groups."""
    trees = [m.node_tree for m in bpy.data.materials if m.node_tree]
    trees += [g for g in bpy.data.node_groups if g.bl_idname == "ShaderNodeTree"]
    return trees


def _group_used_by_other_node(group, node):
    """True when a Colormap node other than ``node`` points at ``group``.

    ``group.users`` cannot tell: a group used by one node already reports
    two users.
    """
    pointer = node.as_pointer()
    return any(
        other.bl_idname == "ShaderNodeValToCMAP"
        and other.node_tree == group
        and other.as_pointer() != pointer
        for tree in _shader_trees()
        for other in tree.nodes
    )


def update_colorramp(node, context):
    """Rewrite the node's Color Ramp from its colormap settings."""
    if not node.colormaps or node.node_tree is None:
        return
    name, library = decode_colormap(node.colormaps)
    colormap = get_colormap(library, name, reverse=node.fcmap)
    apply_colormap(node.color_ramp, colormap, node.n_stops, node.fv_color)


def update_fill_value(node, context):
    """Update only the fill colour, element 0 of the Color Ramp."""
    if node.node_tree is not None:
        set_fill_color(node.color_ramp, node.fv_color)


class BlenderNC_MT_avail_colormaps(bpy.types.Menu):
    """Menu listing every installed colormap, one column group per library."""

    bl_label = "Select Colormap"
    bl_idname = "COLORMAP_MT_menu"

    def draw(self, context):
        """Draw the libraries side by side, wrapping long lists into columns."""
        split = self.layout.split()
        for library, names in available_colormaps().items():
            for start in range(0, len(names), MENU_COLUMN_LENGTH):
                column = split.column()
                column.scale_y = 0.8
                column.label(text=library if start == 0 else "")
                column.separator()
                for name in names[start : start + MENU_COLUMN_LENGTH]:
                    operator = column.operator("blendernc.select_colormap", text=name)
                    operator.node = context.node.name
                    operator.colormap = encode_colormap(name, library)


class BlenderNC_OT_select_colormap(bpy.types.Operator):
    """Set the colormap of a Colormap node."""

    bl_idname = "blendernc.select_colormap"
    bl_label = "Select colormap"
    bl_description = "Select colormap"
    bl_options = {"REGISTER", "UNDO"}

    colormap: bpy.props.StringProperty(name="", default="")
    """Colormap identifier, ``"name:library"``."""

    node: bpy.props.StringProperty(name="", default="")
    """Name of the Colormap node."""

    material: bpy.props.StringProperty(name="", default="")
    """Material holding the node; the edited node tree is used when empty."""

    def _node_tree(self, context):
        """The tree to search: the named material's, or the one being edited."""
        if self.material:
            material = bpy.data.materials.get(self.material)
            return material.node_tree if material else None
        return getattr(context.space_data, "edit_tree", None)

    def execute(self, context):
        """Assign the colormap, which rebuilds the node's Color Ramp."""
        tree = self._node_tree(context)
        node = tree.nodes.get(self.node) if tree else None
        if node is None:
            self.report({"ERROR"}, f"Colormap node {self.node!r} not found.")
            return {"CANCELLED"}
        node.colormaps = self.colormap
        return {"FINISHED"}


class BlenderNC_NT_colormap(bpy.types.ShaderNodeCustomGroup):
    """Shader node mapping a 0 to 1 factor onto a colormap, with a fill colour.

    Missing data is written as 0, so the fill colour (element 0 of the ramp)
    shows where values are missing.
    """

    bl_idname = "ShaderNodeValToCMAP"  # kept from master so saved files still load
    bl_label = "Colormap"

    colormaps: bpy.props.StringProperty(
        default="",
        name="",
        update=update_colorramp,
    )
    """Colormap identifier, ``"name:library"``."""

    n_stops: bpy.props.IntProperty(
        name="# of stops",
        description="Number of color stops",
        default=4,
        min=4,
        max=16,
        update=update_colorramp,
    )
    """Number of colormap samples on the ramp."""

    fcmap: bpy.props.BoolProperty(
        default=False,
        name="Flip cmap",
        update=update_colorramp,
    )
    """Use the reversed colormap."""

    fv_color: bpy.props.FloatVectorProperty(
        name="Fill value color",
        min=0.0,
        max=1.0,
        size=4,
        subtype="COLOR",
        default=[0.0, 0.0, 0.0, 1.0],
        update=update_fill_value,
    )
    """Colour shown for missing data."""

    @property
    def color_ramp(self):
        """The Color Ramp inside this node's group."""
        ramp = next(
            n for n in self.node_tree.nodes if n.bl_idname == "ShaderNodeValToRGB"
        )
        return ramp.color_ramp

    def init(self, context):
        """Create this node's group and apply the default colormap."""
        self.node_tree = _new_colormap_group()
        self.width = 250
        self.colormaps = default_colormap()

    def copy(self, node):
        """Give the copy its own group, so editing one does not change both."""
        self.node_tree = node.node_tree.copy()

    def free(self):
        """Remove this node's group unless another Colormap node uses it."""
        group = self.node_tree
        if group is not None and not _group_used_by_other_node(group, self):
            bpy.data.node_groups.remove(group)

    def draw_buttons(self, context, layout):
        """Draw the colormap menu, its settings and the ramp."""
        name = decode_colormap(self.colormaps)[0] if self.colormaps else None
        layout.menu(BlenderNC_MT_avail_colormaps.bl_idname, text=name)
        layout.prop(self, "n_stops")
        layout.prop(self, "fcmap")
        ramp = next(
            n for n in self.node_tree.nodes if n.bl_idname == "ShaderNodeValToRGB"
        )
        layout.template_color_ramp(ramp, "color_ramp", expand=True)
        layout.prop(self, "fv_color")


class BlenderNC_MT_shader_nodes(bpy.types.Menu):
    """BlenderNC entry in the shader editor's Add menu."""

    bl_label = "BlenderNC"
    bl_idname = "NODE_MT_blendernc_shader"

    def draw(self, context):
        """List BlenderNC's shader nodes."""
        operator = self.layout.operator("node.add_node", text="Colormap")
        operator.type = BlenderNC_NT_colormap.bl_idname
        operator.use_transform = True


def draw_shader_menu(self, context):
    """Append the BlenderNC menu to the shader editor's Add menu."""
    self.layout.separator()
    self.layout.menu(BlenderNC_MT_shader_nodes.bl_idname)
