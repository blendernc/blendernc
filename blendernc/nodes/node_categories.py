from . node_tree import BlenderNCNodeCategory
from nodeitems_utils import  NodeItem

# all categories in a list
node_categories = [
    # identifier, label, items list
    BlenderNCNodeCategory('Shortcuts', "Shortcuts", items=[
        # Create shortcuts,
        NodeItem("netCDFbasincnodes"),
    ]),
    BlenderNCNodeCategory('netCDF', "netCDF", items=[
        # netCDF Input nodes.
        NodeItem("netCDFPath"),
        NodeItem("netCDFNode"),
        NodeItem("netCDFRange"),
    ]),
    BlenderNCNodeCategory('Grid', "Grid", items=[
        # Grid operations
        NodeItem("netCDFinputgrid"),
        NodeItem("netCDFResolution"),
        NodeItem("netCDFrotatelon"),
    ]),
    BlenderNCNodeCategory('Selection', "Selection", items=[
        # Slice and data selection
        #NodeItem("netCDFaxis"),
        NodeItem("netCDFtime"),
    ]),
    BlenderNCNodeCategory('Dimensions', "Dimensions", items=[
        # Dimension operations.
        NodeItem("netCDFdims"),
    ]),
    BlenderNCNodeCategory('Math', "Math", items=[
        # Math Nodes.
        NodeItem("netCDFmath"),
        #NodeItem("netCDFtranspose"),
        #NodeItem("netCDFderivative"),
    ]),
    BlenderNCNodeCategory('Output', "Output", items=[
        # Output Nodes, generate textures and openVDB objects
        NodeItem("netCDFOutput"),
        # NodeItem("netCDFPreloadNode"),
    ])
]
