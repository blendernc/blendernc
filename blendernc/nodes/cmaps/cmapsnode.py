#!/usr/bin/env python3
import bpy

# in blender2.80 use ShaderNodeCategory
from nodeitems_builtins import ShaderNodeCategory
from nodeitems_utils import (
    NodeItem,
    register_node_categories,
    unregister_node_categories,
)

from .utils_colorramp import ColorRamp, update_fill_value

node_group_name = ".Colormaps"

core_colorramp = ColorRamp()


def update_colorramp(self, context):
    if not self.colormaps:
        return
    else:
        cmap_steps = self.n_stops
        selected_cmap = self.colormaps.split(":")
        if self.fcmap:
            selected_cmap[0] = selected_cmap[0] + "_r"
        else:
            if selected_cmap[0].split("_")[-1] == "_r":
                selected_cmap[0] = selected_cmap[0].replace("_r", "")

        colorramp = self.node_tree.nodes[self._get_name("ColorRamp")].color_ramp
        core_colorramp.update_colormap(colorramp, selected_cmap, cmap_steps)


class BlenderNC_MT_avail_colormaps(bpy.types.Menu):
    bl_label = "Select Colormap"
    bl_idname = "COLORMAP_MT_menu"

    def draw(self, context):
        avail_colormaps = core_colorramp.get_cmaps()
        layout = self.layout
        split = layout.split()
        for colormap, map_names in avail_colormaps.items():
            col = split.column()
            col.scale_x = 1
            col.scale_y = 0.8
            col.label(text=colormap)
            col.separator()
            counter = 0
            for map_name in map_names:
                if counter > 15:
                    col = split.column()
                    col.scale_x = 1
                    col.scale_y = 0.8
                    col.label(text="")
                    col.separator()
                    counter = 0
                operator = col.operator(
                    "blendernc.select_colormap", text=map_name, icon="NONE"
                )
                operator.material = context.material.name
                operator.node = context.node.name
                operator.colormap = map_name + ":" + colormap
                counter += 1
            #


# Chosen operator has changed - update the nodes and links
def update_operator(self):
    if bpy.app.version <= (3, 3, 0):
        self.__nodeinterface_setup_bpy3_3__()
    elif bpy.app.version < (4, 0, 0):
        self.__nodeinterface_setup_bpy3__()
    else:
        self.__nodeinterface_setup_bpy4__()
    # Link nodes
    self.__nodetree_setup__()


def create_colormap_nodetree(self):
    # Create node tree
    self.node_tree = core_colorramp.create_group_node(node_group_name)
    # Create group input and output
    input = self.node_tree.nodes.new("NodeGroupInput")
    input.bl_label = self._get_name("Group Input")
    input.name = self._get_name("Group Input")
    output = self.node_tree.nodes.new("NodeGroupOutput")
    output.bl_label = self._get_name("Group Output")
    output.name = self._get_name("Group Output")
    # Create Colormap
    core_colorramp.create_colorramp(self._get_name("ColorRamp"))


def default_colorramp():
    colormaps = core_colorramp.get_cmaps()
    first_colormap = next(iter(colormaps.values()))[0]
    first_colorlib = next(iter(colormaps))
    return first_colormap + ":" + first_colorlib


class BlenderNC_OT_select_colormap(bpy.types.Operator):
    bl_idname = "blendernc.select_colormap"
    bl_label = "Select colormap"
    bl_description = "Select colormap"
    bl_options = {"REGISTER", "UNDO"}

    colormap: bpy.props.StringProperty(
        name="",
        default="",
    )
    """An instance of the original StringProperty."""

    material: bpy.props.StringProperty(
        name="",
        default="",
    )
    """An instance of the original StringProperty."""

    node: bpy.props.StringProperty(
        name="",
        default="",
    )
    """An instance of the original StringProperty."""

    def execute(self, context):
        material = bpy.data.materials.get(self.material)
        colormap_node = material.node_tree.nodes.get(self.node)
        colormap_node.colormaps = self.colormap
        self.bl_label = self.colormap
        return {"FINISHED"}


# for blender > 2.80 and < 4.00 we should derive the class from
# bpy.types.ShaderNodeCustomGroup
class BLENDERNC_CMAPS_NT_node(bpy.types.ShaderNodeCustomGroup):
    bl_idname = "cmapsNode"
    bl_label = "Colormap"
    blb_type = "Blendernc"

    # Manage the node's sockets, adding additional ones when needed,
    # and remove those no longer required
    def __nodeinterface_setup_bpy3_3__(self):
        # Perhaps for dynamic inputs - outputs
        node_tree = self.node_tree
        input_node = node_tree.nodes[self._get_name("Group Input")]
        output_node = node_tree.nodes[self._get_name("Group Output")]

        if hasattr(input_node, "inputs"):
            if input_node.inputs.__len__() != 0:
                return

        # Add input socket if it doesn't exist
        if not input_node.inputs.keys() in ["Fac"]:
            input_node.inputs.clear()
            input_node.inputs.new("NodeSocketFloat", "Fac")

        # Add output socket if it doesn't exist
        if not output_node.outputs.keys() in ["Color"]:
            output_node.outputs.clear()
            output_node.outputs.new("NodeSocketColor", "Color")

    def __nodeinterface_setup_bpy3__(self):
        # Perhaps for dynamic inputs - outputs
        node_tree = self.node_tree

        # Add input socket if it doesn't exist
        if not node_tree.inputs.keys() in ["Fac"]:
            node_tree.inputs.clear()
            node_tree.inputs.new("NodeSocketFloat", "Fac")

        # Add output socket if it doesn't exist
        if not node_tree.outputs.keys() in ["Color"]:
            node_tree.outputs.clear()
            node_tree.outputs.new("NodeSocketColor", "Color")

    def __nodeinterface_setup_bpy4__(self):
        node_tree = self.node_tree
        interface = node_tree.interface

        interface.new_socket("Fac", in_out="INPUT", socket_type="NodeSocketFloat")
        interface.new_socket("Color", in_out="OUTPUT", socket_type="NodeSocketColor")

    # Manage the internal nodes to perform the chained operation:
    # clear all the nodes and build from scratch each time.
    def __nodetree_setup__(self):
        # Remove all links and all nodes that aren't Group Input or Group
        input_node = self.node_tree.nodes[self._get_name("Group Input")]
        cmap = self.node_tree.nodes[self._get_name("ColorRamp")]
        output_node = self.node_tree.nodes[self._get_name("Group Output")]

        # Links:
        self.node_tree.links.new(input_node.outputs[0], cmap.inputs[0])
        self.node_tree.links.new(cmap.outputs[0], output_node.inputs[0])

    colormaps: bpy.props.StringProperty(
        default="",
        name="",
        update=update_colorramp,
    )
    """An instance of the original StringProperty."""

    n_stops: bpy.props.IntProperty(
        name="# of stops",
        description="Number of color stops",
        default=4,
        min=4,
        max=16,
        update=update_colorramp,
    )
    """An instance of the original IntProperty."""

    fcmap: bpy.props.BoolProperty(
        default=False,
        name="Flip cmap",
        update=update_colorramp,
    )
    """An instance of the original BoolProperty."""

    fv_color: bpy.props.FloatVectorProperty(
        name="Fill value color",
        min=0.0,
        max=1.0,
        size=4,
        subtype="COLOR",
        default=[0.0, 0.0, 0.0, 1.0],
        update=update_fill_value,
    )
    """An instance of the original FloatVectorProperty."""

    # Setup the node tree and add the group Input and Output nodes
    def init(self, context):
        create_colormap_nodetree(self)
        # Set width of node
        self.width = 250
        self.colormaps = default_colorramp()
        update_operator(self)
        # Update node
        update_colorramp(self, context)

    # Draw the node components
    def draw_buttons(self, context, layout):
        # Display name of colomap.
        if self.colormaps != "":
            change_name = self.colormaps.split(":")[0]
        else:
            change_name = None
        row = layout.row()
        row.menu("COLORMAP_MT_menu", text=change_name)

        layout.prop(self, "n_stops")
        layout.prop(self, "fcmap")

        tnode = self.node_tree.nodes[self._get_name("ColorRamp")]
        layout.template_color_ramp(tnode, "color_ramp", expand=True)
        layout.prop(self, "fv_color")

    # Copy
    def copy(self, node):
        create_colormap_nodetree(self)
        # TODO: There seems to be a bug when copying this node... the node
        # loses its inputs and outputs
        # self.outputs.remove(self.outputs[0])
        self.colormaps = self.colormaps
        update_operator(self)
        print("Copying from node ", node)

    # Free (when node is deleted)
    def free(self):
        id_node = self._node_identifier()
        for node_key in self.node_tree.nodes.keys():
            if id_node in node_key:
                self.node_tree.nodes.remove(self.node_tree.nodes[node_key])

    def update(self):
        pass

    def _node_identifier(self):
        return self.name.split(".")[-1]

    def _get_name(self, name):
        n_split = self.name.split(".")
        # See line 105 of utils_colorramp.py
        if len(n_split) == 1:
            n_id = ""
        else:
            n_id = "." + n_split[-1]
        return name + n_id


class BlenderNC_OT_shadercolorbar(bpy.types.Operator):
    bl_idname = "blendernc.shadercolorbar"
    bl_label = "Colorbar"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        node_name = context.space_data.id.name
        bpy.data.materials[node_name].node_tree.nodes.new("cmapsNode")
        return {"FINISHED"}


class BLENDERNCshadermenu(bpy.types.Menu):
    bl_label = "BlenderNC"
    bl_idname = "BLENDERNC_MT_shadermenu"

    def draw(self, context):
        layout = self.layout
        layout.operator(BlenderNC_OT_shadercolorbar.bl_idname)


def draw_shadermenu(self, context):
    layout = self.layout
    layout.separator()
    layout.menu(BLENDERNCshadermenu.bl_idname)


# TODO Shift this to the blendernc file

newcatlist = [
    ShaderNodeCategory(
        "SH_NEW_CUSTOM",
        "Blendernc",
        items=[
            NodeItem("cmapsNode"),
        ],
    ),
]


def register():
    if bpy.app.version < (4, 0, 0):
        register_node_categories("CUSTOM_NODES", newcatlist)
    else:
        bpy.types.NODE_MT_shader_node_add_all.append(draw_shadermenu)


def unregister():
    if bpy.app.version < (4, 0, 0):
        unregister_node_categories("CUSTOM_NODES")
    else:
        bpy.types.NODE_MT_shader_node_add_all.remove(draw_shadermenu)


# Attempt to unregister our class
# (in case it's already been registered before)
# and then register it again.
try:
    unregister()
except KeyError:
    pass
register()
