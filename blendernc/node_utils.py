import bpy

def create_basic_geometry_node():
    if "BLENDERNC" not in bpy.data.node_groups.keys():
            
        node_tree = bpy.data.node_groups.new("BLENDERNC","GeometryNodeTree")
        
        # ADD NODES: No input node, since we will be creating a grid.
    
        output_node = node_tree.nodes.new("NodeGroupOutput")
        output_node.location = (300, 0)

        DatacubeImport_node = node_tree.nodes.new("BlenderNCNodeDatacubeImport")
        DatacubeImport_node.location = (-300, 0)
        
        # APPLY TO CURRENT OBJECT
        obj = bpy.context.object
        mod = obj.modifiers.new("BlenderNCModifier", "NODES")
        mod.node_group = node_tree
    else:
        node_tree = bpy.data.node_groups.get("BLENDERNC")
        if "Datacube Import" not in node_tree.nodes.keys():
            DatacubeImport_node = node_tree.nodes.new("BlenderNCNodeDatacubeImport")
            DatacubeImport_node.location = (-300, 0)

    return node_tree