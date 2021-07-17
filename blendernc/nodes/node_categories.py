#!/usr/bin/env python3
from nodeitems_utils import NodeItem

from .node_tree import BlenderNCNodeCategory

node_dicts = {
    "Shortcuts": {
        "name": "Shortcuts",
        "items": ["datacubeBasicNodes"],
    },
    "Datacube": {
        "name": "Datacube",
        "items": ["datacubePath", "datacubeNode", "datacubeRange", "Datacube_tutorial"],
    },
    "Grid": {
        "name": "Grid",
        "items": ["datacubeInputGrid", "datacubeResolution", "datacubeRotatelon"],
    },
    "Selection": {
        "name": "Selection",
        "items": ["datacubeAxis", "datacubeTime"],
    },
    "Dimensions": {
        "name": "Dimensions",
        "items": ["datacubeDims", "datacubeSort"],
    },
    "Math": {
        "name": "Math",
        "items": ["datacubeMath"],  # 'datacubeTranspose','datacubeDerivative'],
    },
    # 'Vectors':{
    #     'name':'Vectors',
    #     'items':['datacubeLic'],
    # },
    "Output": {
        "name": "Output",
        "items": ["datacubeOutput"],  # datacubePreloadNode
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
