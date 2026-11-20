"""Slicing records: how Select, Slice, Subsample and Resolution nodes
describe their selection, and how it is applied to a dataset.

Nothing here imports Blender (see :mod:`blendernc.core`).
"""

import logging
from math import ceil

import numpy as np

logger = logging.getLogger(__name__)


# Encoding of the ``BNC_data.slicing`` string: ``"<var>|<coord>|<spec>,"``.
SLICING_RECORD_SEP = ","


SLICING_FIELD_SEP = "|"


SLICING_ANY_VARIABLE = "*"


# Largest number of samples a surface dimension keeps with the suggested stride.
MAX_VERTEX_SAMPLES = 1000


def suggested_stride(sizes):
    """Smallest stride keeping every surface dimension within the sample budget.

    Parameters
    ----------
    sizes : list of int
        Sizes of the surface dimensions.

    Returns
    -------
    int
        ``ceil(min(sizes) / MAX_VERTEX_SAMPLES)``, at least 1.
    """
    if not sizes:
        return 1
    return max(1, ceil(min(sizes) / MAX_VERTEX_SAMPLES))


def encode_slicing_record(var_name, coord, selector):
    """Encode one ``slicing`` record as ``"<var>|<coord>|<spec>,"``.

    Parameters
    ----------
    var_name : str
        Variable the record applies to, or ``SLICING_ANY_VARIABLE`` for every
        array that has the dimension (coordinates included).
    coord : str
        Dimension or coordinate name.
    selector : int or slice
        Index to pick, or stride to apply. ``slice(0, None, 2)`` is stored as
        ``"0::2"``; ``None`` bounds are left empty.

    Returns
    -------
    str
        The record, including its trailing separator.
    """
    if isinstance(selector, slice):
        bounds = (selector.start, selector.stop, selector.step)
        spec = ":".join("" if b is None else str(b) for b in bounds)
    else:
        spec = str(int(selector))
    return SLICING_FIELD_SEP.join((var_name, coord, spec)) + SLICING_RECORD_SEP


def merge_selector(previous, selector):
    """Combine ``selector`` with the one recorded before it on the same dims.

    A range (``start:stop``) and a stride (``0::step``) are independent, so
    a new range keeps an earlier stride and a new stride keeps an earlier
    range. Anything else, an index in particular, replaces what was there.
    """
    if not (isinstance(previous, slice) and isinstance(selector, slice)):
        return selector
    if selector.step is None:  # a range
        return slice(selector.start, selector.stop, previous.step)
    if not selector.start and selector.stop is None:  # a stride
        return slice(previous.start, previous.stop, selector.step)
    return selector


def recorded_selector(dataset, slicing, var_name, key):
    """Return the selector ``slicing`` holds for the dimensions of ``key``.

    Records may name the dimension or a coordinate on it, so they are
    compared by the dimensions they resolve to. ``None`` when there is none.
    """
    dims = _dims_for_key(dataset, key) if dataset is not None else (key,)
    if not dims:
        return None
    found = None
    for other, selector in parse_slicing(slicing, var_name).items():
        other_dims = _dims_for_key(dataset, other) if dataset is not None else (other,)
        if other_dims == dims:
            found = selector
    return found


def clamp_index_range(size, first, last):
    """Return ``(first, last)`` clamped to ``0 .. size - 1`` and in order."""
    first, last = sorted((min(first, size - 1), min(last, size - 1)))
    return max(first, 0), max(last, 0)


def value_index_range(values, low, high):
    """First and last position of the ``values`` within ``[low, high]``.

    Node properties hold single-precision floats, so the bounds are widened
    by a relative tolerance that absorbs their rounding.

    Parameters
    ----------
    values : numpy.ndarray
        1-D numeric coordinate values, normally monotonic.
    low, high : float
        Bounds, in either order.

    Returns
    -------
    tuple of int or None
        ``(first, last)``, or ``None`` when no value is in range.
    """
    values = np.asarray(values, dtype=np.float64)
    low, high = sorted((low, high))
    tolerance = 1e-6 * max(abs(low), abs(high))
    inside = np.flatnonzero((values >= low - tolerance) & (values <= high + tolerance))
    if inside.size == 0:
        return None
    return int(inside[0]), int(inside[-1])


def format_coord_value(value):
    """Short text for one coordinate value: dates to the second, numbers to 6 digits."""
    if np.issubdtype(np.asarray(value).dtype, np.datetime64):
        return str(np.datetime64(value, "s"))
    if np.issubdtype(np.asarray(value).dtype, np.number):
        return f"{float(value):.6g}"
    return str(value)


def _decode_selector(spec):
    """Turn ``"i"`` into ``int`` and ``"start:stop:step"`` into ``slice``."""
    if ":" not in spec:
        return int(spec)
    parts = [int(p) if p else None for p in spec.split(":")]
    parts += [None] * (3 - len(parts))
    return slice(*parts[:3])


def parse_slicing(slicing, var_name):
    """Collect the selectors in ``slicing`` that apply to ``var_name``.

    Later records override earlier ones for the same coordinate.

    Returns
    -------
    dict
        Mapping of dimension or coordinate name to ``int`` or ``slice``.
    """
    indexers = {}
    for record in filter(None, slicing.split(SLICING_RECORD_SEP)):
        fields = record.split(SLICING_FIELD_SEP)
        if len(fields) != 3:
            logger.warning(f"Ignoring malformed slicing record {record!r}")
            continue
        target, coord, spec = fields
        if target in (var_name, SLICING_ANY_VARIABLE):
            indexers[coord] = _decode_selector(spec)
    return indexers


def _dims_for_key(dataset, key):
    """Dimensions a slicing key refers to: itself, or those of a coordinate."""
    if key in dataset.dims:
        return (key,)
    if key in dataset.coords:
        return dataset[key].dims
    return ()


def build_indexers(dataset, data, slicing, var_name):
    """Map the slicing records for ``var_name`` onto the dims ``data`` has.

    Parameters
    ----------
    dataset : xarray.Dataset
        Dataset used to resolve coordinate names to dimensions.
    data : xarray.DataArray
        Array the indexers will be applied to.
    slicing : str
        Encoded ``slicing`` string of a ``BNC_data`` item.
    var_name : str
        Name of ``data`` inside ``dataset``.

    Returns
    -------
    dict
        Mapping of dimension name to ``int`` or ``slice`` for ``isel``.
    """
    selectors = parse_slicing(slicing, var_name)
    return {
        dim: selector
        for key, selector in selectors.items()
        for dim in _dims_for_key(dataset, key)
        if dim in data.dims
    }
