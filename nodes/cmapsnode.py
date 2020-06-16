import bpy

from . utils_colorramp import ColorRamp

node_group_name = ".NodeGroup"

core_colorramp = ColorRamp()


def update_colorramp(self, context):
    update_operator(self,context)
    cmap_steps = self.n_stops
    selected_cmap = self.colormaps.split('.')
    if self.fcmap:
        selected_cmap[0] = selected_cmap[0]+'_r'
    else:
        selected_cmap[0] = selected_cmap[0].split('_')[0]
    core_colorramp.update_colormap(selected_cmap,cmap_steps)

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

    bl_idname = 'cmapsNode'
    bl_label = 'Colormap'
    blb_type = 'Blendernc'   

    # Manage the node's sockets, adding additional ones when needed and removing those no longer required
    def __nodeinterface_setup__(self):
        # Perhaps for dynamic inputs - outputs            
        if self.node_tree.inputs:
            return

        # Add input socket if it doesn't exist
        if not self.node_tree.inputs.keys() in ['Fac']:
            self.node_tree.inputs.clear()
            self.node_tree.inputs.new("NodeSocketFloat", "Fac")

        # Add output socket if it doesn't exist
        if not self.node_tree.outputs.keys() in ['Color']:
            self.node_tree.outputs.clear()
            self.node_tree.outputs.new("NodeSocketColor", "Color")

    
    
    # Manage the internal nodes to perform the chained operation - clear all the nodes and build from scratch each time.
    def __nodetree_setup__(self):
        # Remove all links and all nodes that aren  't Group Input or Group Output
        #self.node_tree.links.clear()
        #pass
        input_node = self.node_tree.nodes[self._get_name('Group Input')]

        ## ADD math here:
        cmap = self.node_tree.nodes[self._get_color_ramp_node_name()]

        output_node = self.node_tree.nodes[self._get_name('Group Output')]

        # Links:
        self.node_tree.links.new(input_node.outputs[0],cmap.inputs[0])
        self.node_tree.links.new(cmap.outputs[0],output_node.inputs[0])
    
    colormaps: bpy.props.EnumProperty(
        items=core_colorramp.get_colormaps(),
        name="",
        update=update_colorramp,
    )

    n_stops: bpy.props.IntProperty(
        name='# of stops', 
        description='Number of color stops',
        default=4,
        min=4,
        max=16,
        update=update_colorramp,
    )
    
    vmin: bpy.props.FloatProperty(
         default=0,
         name="vmin",
         update=update_colorramp,
    )

    vmax: bpy.props.FloatProperty(
        default=1,
        name="vmax",
        update=update_colorramp,
    )

    fcmap: bpy.props.BoolProperty(
        default=False,
        name="Flip cmap",
        update=update_colorramp,
    )

    # Setup the node - setup the node tree and add the group Input and Output nodes
    def init(self, context):
        # Create node tree
        self.node_tree = core_colorramp.create_group_node(node_group_name)
        # Create group input and output
        self.node_tree.nodes.new('NodeGroupInput')
        self.node_tree.nodes.new('NodeGroupOutput')
        # Create Colormap
        core_colorramp.create_colorramp(self._get_color_ramp_node_name())
        # Set width of node
        self.width = 250
        # Update node
        update_colorramp(self, context)

    # Draw the node components
    def draw_buttons(self, context, layout):
        row=layout.row()
        row.prop(self, 'colormaps', text='')
        layout.prop(self, "n_stops")
        layout.prop(self, "fcmap")

        tnode = self.node_tree.nodes[self._get_color_ramp_node_name()]
        layout.template_color_ramp(tnode, "color_ramp", expand=True)

        row=layout.row()
        row.prop(self, "vmin")
        row.prop(self, "vmax")

    # Copy
    def copy(self, node):
        print("Copying from node ", node)
        self.node_tree=node.node_tree.copy()

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
        # color_output=self.outputs
        # self.__nodeinterface_setup__()
        # self.__nodetree_setup__()

        # cmap_steps = self.n_stops
        # selecteAd_cmap = self.colormaps.split('.')
        # core_colorramp.update_colormap(selected_cmap,cmap_steps)

    def _get_color_ramp_node_name(self):
        n_split = self.name.split('.')
        if len(n_split) == 1:
            n_id="000"
        else:
            n_id=n_split[-1]
        return 'Color_Ramp'+"."+n_id 
    
    def _node_identifier(self):
        return self.name.split('.')[-1]
    
    def _get_name(self,name):
        n_split = self.name.split('.')
        if len(n_split) == 1:
            n_id=""
        else:
            n_id="."+n_split[-1]
        return name+n_id




from nodeitems_utils import NodeItem, register_node_categories, unregister_node_categories
# in blender2.80 use ShaderNodeCategory
from nodeitems_builtins import ShaderNodeCategory

def register():
    #bpy.utils.register_class(MathsDynamic)
    newcatlist = [ShaderNodeCategory("SH_NEW_CUSTOM", "Blendernc", items=[NodeItem("cmapsNode"),]),]
    register_node_categories("CUSTOM_NODES", newcatlist)

def unregister():
    unregister_node_categories("CUSTOM_NODES")
    #bpy.utils.unregister_class(MathsDynamic)

# Attempt to unregister our class (in case it's already been registered before) and register it.
try :
    unregister()
except:
    pass
register() 