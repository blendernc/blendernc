import bpy

from .utils_colorramp import ColorRamp, update_fill_value

node_group_name = ".Colormaps"

core_colorramp = ColorRamp()


def update_colorramp(self, context):
    update_operator(self, context)
    cmap_steps = self.n_stops
    selected_cmap = self.colormaps.split(":")
    if self.fcmap:
        selected_cmap[0] = selected_cmap[0] + "_r"
    else:
        if selected_cmap[0].split("_")[-1] == "_r":
            selected_cmap[0] = selected_cmap[0].replace("_r", "")

    if len(self.node_tree.nodes[:]) == 3:
        colorramp = self.node_tree.nodes["Color_Ramp.000"].color_ramp
    else:
        colorramp = self.node_tree.nodes[self._get_name("Color_Ramp")].color_ramp
    core_colorramp.update_colormap(colorramp, selected_cmap, cmap_steps)


# Chosen operator has changed - update the nodes and links
def update_operator(self, context):
    self.__nodeinterface_setup__()
    self.__nodetree_setup__()


# Number of inputs has changed - update the nodes and links
def update_inpSockets(self, context):
    self.__nodeinterface_setup__()
    self.__nodetree_setup__()


# for blender2.80 we should derive the class from bpy.types.ShaderNodeCustomGroup
class BLENDERNC_CMAPS_NT_node(bpy.types.ShaderNodeCustomGroup):

    bl_idname = "cmapsNode"
    bl_label = "Colormap"
    blb_type = "Blendernc"

    # Manage the node's sockets, adding additional ones when needed and removing those no longer required
    def __nodeinterface_setup__(self):
        # Perhaps for dynamic inputs - outputs
        if self.node_tree.inputs:
            return

        # Add input socket if it doesn't exist
        if not self.node_tree.inputs.keys() in ["Fac"]:
            self.node_tree.inputs.clear()
            self.node_tree.inputs.new("NodeSocketFloat", "Fac")

        # Add output socket if it doesn't exist
        if not self.node_tree.outputs.keys() in ["Color"]:
            self.node_tree.outputs.clear()
            self.node_tree.outputs.new("NodeSocketColor", "Color")

    # Manage the internal nodes to perform the chained operation - clear all the nodes and build from scratch each time.
    def __nodetree_setup__(self):
        # Remove all links and all nodes that aren  't Group Input or Group Output
        if len(self.node_tree.nodes[:]) == 3:
            input_node = self.node_tree.nodes["Group Input.000"]
            ## TODO: ADD math here to control max and min values
            cmap = self.node_tree.nodes["Color_Ramp.000"]
            output_node = self.node_tree.nodes["Group Output.000"]
        else:
            input_node = self.node_tree.nodes[self._get_name("Group Input")]
            ## TODO: ADD math here to control max and min values
            cmap = self.node_tree.nodes[self._get_name("Color_Ramp")]
            output_node = self.node_tree.nodes[self._get_name("Group Output")]

        # Links:
        self.node_tree.links.new(input_node.outputs[0], cmap.inputs[0])
        self.node_tree.links.new(cmap.outputs[0], output_node.inputs[0])

    colormaps: bpy.props.EnumProperty(
        items=core_colorramp.get_colormaps(),
        name="",
        update=update_colorramp,
    )

    n_stops: bpy.props.IntProperty(
        name="# of stops",
        description="Number of color stops",
        default=4,
        min=4,
        max=16,
        update=update_colorramp,
    )

    fcmap: bpy.props.BoolProperty(
        default=False,
        name="Flip cmap",
        update=update_colorramp,
    )

    fv_color: bpy.props.FloatVectorProperty(
        name="Fill value color",
        min=0.0,
        max=1.0,
        size=4,
        subtype="COLOR",
        default=[0.0, 0.0, 0.0, 1.0],
        update=update_fill_value,
    )

    # Setup the node - setup the node tree and add the group Input and Output nodes
    def init(self, context):
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
        core_colorramp.create_colorramp(self._get_name("Color_Ramp"))
        # Set width of node
        self.width = 250
        # Update node
        update_colorramp(self, context)

    # Draw the node components
    def draw_buttons(self, context, layout):
        row = layout.row()
        row.prop(self, "colormaps", text="")
        layout.prop(self, "n_stops")
        layout.prop(self, "fcmap")

        if len(self.node_tree.nodes[:]) == 3:
            tnode = self.node_tree.nodes["Color_Ramp.000"]
        else:
            tnode = self.node_tree.nodes[self._get_name("Color_Ramp")]
        layout.template_color_ramp(tnode, "color_ramp", expand=True)
        layout.prop(self, "fv_color")

    # Copy
    def copy(self, node):
        print("Copying from node ", node)
        self.node_tree = node.node_tree.copy()

    # Free (when node is deleted)
    def free(self):
        # Free node group
        if len(self.node_tree.nodes.keys()) <= 3:
            bpy.data.node_groups.remove(self.node_tree, do_unlink=True)
        else:
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
        n_id = ".000"
        # See line 105 of utils_colorramp.py
        # if len(n_split) == 1:
        #     n_id=".000"
        # else:
        #     n_id='.'+n_split[-1]
        return name + n_id


from nodeitems_utils import (
    NodeItem,
    register_node_categories,
    unregister_node_categories,
)

# in blender2.80 use ShaderNodeCategory
from nodeitems_builtins import ShaderNodeCategory


def register():
    newcatlist = [
        ShaderNodeCategory(
            "SH_NEW_CUSTOM",
            "Blendernc",
            items=[
                NodeItem("cmapsNode"),
            ],
        ),
    ]
    register_node_categories("CUSTOM_NODES", newcatlist)


def unregister():
    unregister_node_categories("CUSTOM_NODES")


# Attempt to unregister our class (in case it's already been registered before) and register it.
try:
    unregister()
except:
    pass
register()
