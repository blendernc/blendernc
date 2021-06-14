#!/usr/bin/env python3


def get_unique_data_dict(node):
    # Replaces all node.blendernc_dict[unique_identifier]
    # TODO: Make sure to replace all the unique data dicts
    data_dictionary = node.blendernc_dict
    unique_identifier = node.blendernc_dataset_identifier
    unique_data_dict = data_dictionary[unique_identifier]
    return unique_data_dict
