from . node_tree import BlenderNCNodeCategory
from nodeitems_utils import  NodeItem

# all categories in a list
node_categories = [
    # identifier, label, items list
    BlenderNCNodeCategory('netCDF', "netCDF", items=[
        # our basic node
        NodeItem("netCDFNode"),
        NodeItem("netCDFPath"),
    ]),
    BlenderNCNodeCategory('Grid', "Grid", items=[
        # our basic node
        NodeItem("netCDFResolution"),
    ]),
    BlenderNCNodeCategory('Selection', "Selection", items=[
        # our basic node
        NodeItem("netCDFaxis"),
        NodeItem("netCDFdims"),
    ]),
    BlenderNCNodeCategory('Math', "Math", items=[
        # our basic node
        NodeItem("netCDFtranspose"),
        NodeItem("netCDFderivative"),
    ]),
    BlenderNCNodeCategory('Output', "Output", items=[
        # our basic node
        NodeItem("netCDFOutput"),
        NodeItem("netCDFPreloadNode"),
    ])
]
