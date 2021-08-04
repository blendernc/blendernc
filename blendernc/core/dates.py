#!/usr/bin/env python3
import numpy as np

from ..python_functions import build_enum_prop_list, refresh_cache
from .update_ui import update_value_and_node_tree


def get_items_datetimes(self, context):
    if self.inputs[0].is_linked and self.inputs[0].links:
        # BlenderNC dictionary
        blendernc_dict = (
            self.inputs[0]
            .links[0]
            .from_node.blendernc_dict[self.blendernc_dataset_identifier]
            .copy()
        )
        # BlenderNC dataset
        dataset = blendernc_dict["Dataset"]
        # BlenderNC times
        datetimes = dataset["time"]
        return datetimes.values


def get_item_time(self, context):
    times = get_items_datetimes(self, context)
    return build_enum_prop_list(times, start=0)


def get_item_days(self, context):
    datetimes = get_items_datetimes(self, context)
    if "datetime64" not in str(datetimes.dtype):
        return []
    if self.selected_time == "":
        selected_time = min(datetimes)
        selected_year = dt2cal(selected_time)[0]  # year
        selected_month = dt2cal(selected_time)[1]  # month
    elif self.selected_time in np.array(datetimes, dtype=str):
        selected_time = np.datetime64(self.selected_time).astype(object)
        selected_year = dt2cal(selected_time)[0]
        selected_month = dt2cal(selected_time)[1]
    else:
        selected_time = min(datetimes)
        selected_year = dt2cal(selected_time)[0]  # year
        selected_month = dt2cal(selected_time)[1]  # month

    dataset_days_in_month = days_in_month(datetimes, selected_month, selected_year)

    return build_enum_prop_list(dataset_days_in_month, start=0)


def days_in_month(datetimes, selected_month, selected_year):
    dataset_days_in_month = []
    for datetime in datetimes:
        if (
            dt2cal(datetime)[1] == selected_month
            and dt2cal(datetime)[0] == selected_year
        ):
            dataset_days_in_month.append(dt2cal(datetime)[2])
        else:
            break
    return dataset_days_in_month


def get_item_month(self, context):
    datetimes = get_items_datetimes(self, context)
    if "datetime64" not in str(datetimes.dtype):
        return []
    if self.selected_time == "":
        selected_time = min(datetimes)
        selected_year = dt2cal(selected_time)[0]
    elif self.selected_time in np.array(datetimes, dtype=str):
        selected_time = np.datetime64(self.selected_time)
        selected_year = dt2cal(selected_time)[0]
    else:
        selected_time = min(datetimes)
        selected_year = dt2cal(selected_time)[0]
        # TODO report ERROR
        # self.report({'Error'}, "Day out of range!")
    cal = dt2cal(datetimes)
    dataset_months_in_years = np.unique(cal[:, 1][cal[:, 0] == selected_year])

    return build_enum_prop_list(dataset_months_in_years, start=0)


def get_item_year(self, context):
    datetimes = get_items_datetimes(self, context)
    dataset_years = np.unique(dt2cal(datetimes)[:, 0])
    return build_enum_prop_list(dataset_years, start=0)


def update_date(self, context):
    NodeTree = self.rna_type.id_data.name
    identifier = self.blendernc_dataset_identifier
    if self.day and self.month and self.year:
        self.selected_time = return_date(self.day, self.month, self.year)
        refresh_cache(NodeTree, identifier, context.scene.frame_current)
        update_value_and_node_tree(self, context)

    elif self.step:
        self.selected_time = self.step
        refresh_cache(NodeTree, identifier, context.scene.frame_current)
        update_value_and_node_tree(self, context)


def return_date(day, month, year, hour=""):
    return "%d-%02d-%02d" % (
        int(year),
        int(month),
        int(day),
    )  # "{2}-{1:02s}-{0:02s}".format(day,month,year)


def dt2cal(dt):
    """
    Convert array of datetime64 to a calendar array of year, month, day, hour,
    minute, seconds, microsecond with these quantites indexed on the last axis.

    Parameters
    ----------
    dt : datetime64 array (...)
        numpy.ndarray of datetimes of arbitrary shape

    Returns
    -------
    cal : uint32 array (..., 7)
        calendar array with last axis representing year, month, day, hour,
        minute, second, microsecond
    """

    # allocate output
    out = np.empty(dt.shape + (7,), dtype="u4")
    # decompose calendar floors
    Y, M, D, h, m, s = [dt.astype(f"M8[{x}]") for x in "YMDhms"]
    out[..., 0] = Y + 1970  # Gregorian Year
    out[..., 1] = (M - Y) + 1  # month
    out[..., 2] = (D - M) + 1  # dat
    out[..., 3] = (dt - D).astype("m8[h]")  # hour
    out[..., 4] = (dt - h).astype("m8[m]")  # minute
    out[..., 5] = (dt - m).astype("m8[s]")  # second
    out[..., 6] = (dt - s).astype("m8[us]")  # microsecond
    return out
