import glob
import logging
import os.path

import bpy
import xarray as xr

from .decorators import check_if_node_tree_exists


def get_datacube_path(directory, files):
    """
    Get the datacube path based on the provided directory and files.

    Parameters:
        directory (str): The directory where the files are located.
        files (list): A list of file names.
    """
    if len(files) == 1:
        datacube_path = os.path.join(directory, files[0].name)
    else:
        filenames = [f.name for f in files]
        common_name = findCommonName(filenames)
        datacube_path = os.path.join(directory, common_name)
    return datacube_path


@check_if_node_tree_exists
def create_datastruct(self, context):
    node_tree = bpy.data.node_groups.get(self.node_tree)
    filepath_string_node = node_tree.nodes.get(self.node_name)

    BNC_datastructs = filepath_string_node.BNC_datastructs[0]
    BNC_datastructs.datafile = filepath_string_node.datacube_file
    BNC_datastructs.filename = filepath_string_node.datacube_file.split("/")[-1]
    BNC_datastructs.dict[BNC_datastructs.filename] = load_dataset(
        BNC_datastructs.datafile
    )


def load_dataset(filepath):
    """
    Load a dataset using xarray and return the dataset object.

    Parameters:
        filepath (str): The path to the dataset file.
    """
    logging.info(f"Loading dataset from {filepath}")
    if glob.glob(filepath):
        dataset = xr.open_mfdataset(filepath)
    else:
        raise NameError(f"File {filepath} does not exist")
    return dataset


def name_match(block, cfname, filename):
    if not cfname and (block.a != 0 or block.b != 0):
        raise ValueError("Start of filename strings do not match.")
    elif block.a == block.b and block.size != 0:
        if len(cfname) != 0 and len(cfname) != block.a:
            cfname += "*"
        cfname += filename[block.a : block.a + block.size]
    elif cfname or block.a != block.b:
        pass
    return cfname


def findCommonName(filenames):
    import difflib

    cfname = []
    fcounter = 0
    while len(filenames) - 1 > fcounter:
        S = difflib.SequenceMatcher(None, filenames[fcounter], filenames[fcounter + 1])
        cname = ""
        for block in S.get_matching_blocks():
            cname = name_match(block, cname, filenames[fcounter])
        cfname.append(cname)
        fcounter += 1
    commonName = min(cfname, key=len)
    if "*" not in commonName:
        raise ValueError("Filenames do not match")
    if commonName[-1] == ".":
        raise ValueError("Filenames formats do not match")
    return commonName


def get_possible_variables(node, context):
    datastruct = node.BNC_datastructs[0]
    if not datastruct.dict and not datastruct.filename:
        return empty_item()
    datacubedata = datastruct.dict[datastruct.filename]
    items = get_var(datacubedata)
    return items


def get_var(datacubedata, str_filter=None):
    """
    get_var _summary_

    Parameters
    ----------
    datacubedata : _type_
        _description_
    str_filter : List, optional
        _description_, by default None

    Returns
    -------
    _type_
        _description_
    """
    dimensions = sorted(list(datacubedata.coords.keys()))
    variables = sorted(list(datacubedata.variables.keys() - dimensions))

    if str_filter is not None:
        variables = filter_2_string_lists(variables, str_filter)

    if "long_name" in datacubedata[variables[0]].attrs:
        long_name_list = [
            (
                datacubedata[var].attrs["long_name"]
                if "long_name" in datacubedata[var].attrs
                else ""
            )
            for var in variables
        ]
        var_names = build_enum_prop_list(variables, "DISK_DRIVE", long_name_list)
    else:
        var_names = build_enum_prop_list(variables, "DISK_DRIVE")
    return select_item() + [None] + var_names


def build_enum_prop_list(list, icon="NONE", long_name_list=None, start=1):
    if long_name_list:
        list = [
            (str(list[ii]), str(list[ii]), long_name_list[ii], icon, ii + start)
            for ii in range(len(list))
        ]
    else:
        list = [
            (str(list[ii]), str(list[ii]), str(list[ii]), icon, ii + start)
            for ii in range(len(list))
        ]
    return list


def filter_2_string_lists(list, str_filter):
    tmp_list = []
    for strfit in str_filter:
        for item in list:
            if strfit in item.lower() and "" in item.lower().split(strfit):
                tmp_list.append(item)
    return tmp_list


def select_item():
    return [("No var", "Select variable", "Empty", "NODE_SEL", 0)]


def empty_item():
    return [("No var", "No variable", "Empty", "CANCEL", 0)]
