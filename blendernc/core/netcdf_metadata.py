#!/usr/bin/env python3
def get_items_dims(self, context):
    if self.inputs[0].is_linked and self.inputs[0].links and self.blendernc_dict:
        # BlenderNC dictionary
        blendernc_dict = (
            self.inputs[0]
            .links[0]
            .from_node.blendernc_dict[self.blendernc_dataset_identifier]
            .copy()
        )
        # BlenderNC dataset
        dataset = blendernc_dict["Dataset"]
        # BlenderNC var
        var = blendernc_dict["selected_var"]["selected_var_name"]
        # Extract dataset axis
        dims = dataset[var].dims
        return dims


def get_items_axes(self, context):
    dims = get_items_dims(self, context)
    dims_list = []
    counter = 0
    for dim in dims:
        dims_list.append((str(dim), str(dim), str(dim), "EMPTY_DATA", counter))
        counter += 1
    return dims_list
