import bpy
import importlib

NODE_TYPE =  'ShaderNodeValToRGB'

def divide_cmap(n,step):
    return (n-1)*(1/(step-1)),int((n-1)*(256//(step-1)))

def update_fill_value(node,context):
    colorramp = node.node_tree.nodes.get('Color_Ramp.000').color_ramp
    colorramp.elements[0].color = node.fv_color

class ColorRamp(object):
    def __init__(self):
        self.cmaps = self.installed_cmaps()
    
    def installed_cmaps(self):
        import importlib   
        cmaps = []
        import matplotlib
        matplotlib.use('Agg')
        try:
            import cmocean as cmocean
            cmaps.append('cmocean')
        except ImportError as importerror:
            raise importerror
            # TODO: Raise error in UI. 
        try:
            from matplotlib import cm
            cmaps.append('matplotlib')
        except ImportError as importerror:
            raise importerror
            # TODO: Raise error in UI. 

        return cmaps

    def get_colormaps(self):
        names = self.get_cmaps()
        cmap_names = []
        counter=0
        for key,items in names.items():
            for item in items:
                cmap_names.append((item+":"+key,item+" - "+key,"",counter))
                counter+=1
        return cmap_names
        #[(cmaps[ii],cmaps[ii],"",ii) for ii in range(len(cmaps))]

    def get_cmaps(self):
        import importlib
        names={}
        for maps in self.cmaps:
            cmap = importlib.import_module(maps)
            if maps == "cmocean":
                names['cmocean']=cmap.cm.cmapnames
            else:
                names['matplotlib']=[ii for ii in cmap.cm.cmap_d.keys() if '_r' not in ii ]
        return names

    def update_colormap(self,color_ramp,selected_cmap,cmap_steps):
        #self.node.color_ramp.elements[1].color[0:3]=getattr(cmap.cm, selected_cmap)(int(0))[0:3]
        #self.node.color_ramp.elements[0].color[0:3]=getattr(cmap.cm, selected_cmap)(int(256))[0:3]
        
        #self.get_valid_evaluate_function(node.name)
        self.color_ramp=color_ramp

        print(selected_cmap,cmap_steps)

        cmap_steps = cmap_steps
        s_cmap,maps = selected_cmap
        cmap = importlib.import_module(maps)

        cms = cmap.cm.cmap_d
        
        items = self.color_ramp.elements.items()

        if len(items) != cmap_steps+1:
            # Remove all items descendent to avoid missing points and leave first position.
            [ self.color_ramp.elements.remove(element) for item,element in items[::-1][:-1] ]
            self.color_ramp.elements[0].color=(0,0,0,1)
            self.color_ramp.elements.new(1e-5)
            pos,value = divide_cmap(1e-5,cmap_steps)
            self.color_ramp.elements[1].color = cms.get(s_cmap)(value)
            for i in range(2,cmap_steps+1):
                pos,value = divide_cmap(i,cmap_steps)
                self.color_ramp.elements.new(pos)
                #
                self.color_ramp.elements[i].position = pos
                self.color_ramp.elements[i].color = cms.get(s_cmap)(value)
        else: 
            self.color_ramp.elements[0].color=(0,0,0,1)
            #
            self.color_ramp.elements[0].position = 0
            self.color_ramp.elements.new(1e-5)
            pos,value = divide_cmap(1e-5,cmap_steps)
            self.color_ramp.elements[1].color = cms.get(s_cmap)(value)
            #
            self.color_ramp.elements[1].position = pos
            for i in range(2,cmap_steps+1):
                pos,value = divide_cmap(i,cmap_steps)
                #
                self.color_ramp.elements[i].position = pos
                self.color_ramp.elements[i].color = cms.get(s_cmap)(value)

    def create_group_node(self,group_name):
        self.group_name = group_name
        self.node_groups = bpy.data.node_groups
        # make sure the node-group is present
        group = self.node_groups.get(self.group_name)
        # Uncoment to create nodes only when duplicating the node. 
        # This was commented as it created issues with multiple colormap nodes
        # sharing the same node output.
        #if not group:
        group = self.node_groups.new(self.group_name, 'ShaderNodeTree')
        #group.use_fake_user = True
        self.group_name = group.name
        return group

    def create_colorramp(self,node_name):        
        colorramp_node = self.get_valid_evaluate_function(node_name)

    def get_valid_node(self,node_name):
        self.node_name = node_name
        self.node_groups = bpy.data.node_groups
        # make sure the node-group is present
        group = self.node_groups.get(self.group_name)
        if not group:
            group = self.node_groups.new(self.group_name, 'ShaderNodeTree')
        group.use_fake_user = True

        # make sure the color_rampNode we want to use is present too
        node = group.nodes.get(self.node_name)
        if not node:
            node = group.nodes.new(NODE_TYPE)
            node.name = self.node_name

        return node


    def get_valid_evaluate_function(self,node_name):
        '''
        Takes a material-group name and a Node name it expects to find.
        The node will be of type ShaderNodeValToRGB and this function
        will force its existence, then return the evaluate function.
        '''
        self.node = self.get_valid_node(node_name)

        self.color_ramp = self.node.color_ramp
        
        try: self.color_ramp.evaluate(0.0)
        except: self.color_ramp.initialize()

        evaluate = lambda val: self.color_ramp.evaluate(val)
        return evaluate
