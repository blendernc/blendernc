#!/usr/bin/env python3
from nodeitems_utils import NodeItem

from .node_tree import BlenderNCNodeCategory

node_dicts = {
    "Shortcuts": {
        "name": "Shortcuts",
        "items": ["netCDFbasincnodes"],
    },
    "Datacube": {
        "name": "Datacube",
        "items": ["netCDFPath", "netCDFNode", "netCDFRange", "Datacube_tutorial"],
    },
    "Grid": {
        "name": "Grid",
        "items": ["netCDFinputgrid", "netCDFResolution", "netCDFrotatelon"],
    },
    "Selection": {
        "name": "Selection",
        "items": ["netCDFaxis", "netCDFtime"],
    },
    "Dimensions": {
        "name": "Dimensions",
        "items": ["netCDFdims", "netCDFsort"],
    },
    "Math": {
        "name": "Math",
        "items": ["netCDFmath"],  # 'netCDFtranspose','netCDFderivative'],
    },
    # 'Vectors':{
    #     'name':'Vectors',
    #     'items':['netCDFlic'],
    # },
    "Output": {
        "name": "Output",
        "items": ["netCDFOutput"],  # netCDFPreloadNode
    },
}


def generate_node_cathegories(node_dict):
    node_list = []
    for key, item in node_dict.items():
        node_list.append(
            BlenderNCNodeCategory(
                key,
                item["name"],
                items=[NodeItem(it) for it in item["items"]],
            ),
        )
    return node_list


node_categories = generate_node_cathegories(node_dicts)
