"""Opening datacubes and naming their parts.

Nothing here imports Blender (see :mod:`blendernc.core`).
"""

import difflib
import logging
import os.path

import xarray as xr

logger = logging.getLogger(__name__)


def get_datacube_path(directory, files):
    """Return the path to load for the files picked in the file browser.

    Parameters
    ----------
    directory : str
        Folder holding the files.
    files : bpy_prop_collection
        Picked files, each with a ``name``.

    Returns
    -------
    str
        The file's path when one was picked, otherwise a glob pattern
        matching all of them (see :func:`find_common_name`).
    """
    if len(files) == 1:
        datacube_path = os.path.join(directory, files[0].name)
    else:
        filenames = [f.name for f in files]
        common_name = find_common_name(filenames)
        datacube_path = os.path.join(directory, common_name)
    return datacube_path


# xarray engine by file extension; anything else is left to xarray to detect.
DATASET_ENGINES = {
    ".zarr": "zarr",
    ".grib": "cfgrib",
    ".grib2": "cfgrib",
    ".grb": "cfgrib",
    ".grb2": "cfgrib",
}


def dataset_engine(path):
    """Return the xarray engine for ``path``, or ``None`` to let xarray choose."""
    extension = os.path.splitext(path.rstrip("/\\"))[1].lower()
    return DATASET_ENGINES.get(extension)


def dataset_key(path):
    """Cache key for ``path``: the absolute, normalised path or pattern.

    Two files with the same name in different folders get different keys.
    """
    return os.path.normcase(os.path.abspath(path))


def load_dataset(filepath):
    """Open a file, Zarr store or glob pattern with xarray.

    Parameters
    ----------
    filepath : str
        Path or pattern accepted by :func:`xarray.open_mfdataset`. GRIB and
        Zarr inputs get their engine from :func:`dataset_engine`.

    Returns
    -------
    xarray.Dataset

    Raises
    ------
    OSError
        If nothing matches ``filepath`` or a file cannot be read.
    ValueError
        If no xarray backend understands the file.
    """
    engine = dataset_engine(filepath)
    logger.info(f"Loading dataset from {filepath} (engine: {engine or 'auto'})")
    kwargs = {"engine": engine} if engine else {}
    return xr.open_mfdataset(filepath, **kwargs)


def name_match(block, cfname, filename):
    """Extend a glob pattern with one matching block from ``difflib``.

    Parameters
    ----------
    block : difflib.Match
        Matching block ``(a, b, size)`` between two filenames.
    cfname : str
        Pattern built so far.
    filename : str
        Filename the block indices ``a`` refer to.

    Returns
    -------
    str
        ``cfname`` extended with the matched text, preceded by ``"*"`` when a
        gap separates it from the previous block.

    Raises
    ------
    ValueError
        If the first block does not start at the beginning of both names.
    """
    if not cfname and (block.a != 0 or block.b != 0):
        raise ValueError("Start of filename strings do not match.")
    elif block.a == block.b and block.size != 0:
        if len(cfname) != 0 and len(cfname) != block.a:
            cfname += "*"
        cfname += filename[block.a : block.a + block.size]
    return cfname


def find_common_name(filenames):
    """Build a glob pattern matching a list of similar filenames.

    Consecutive filenames are compared and the shortest common pattern is
    kept, e.g. ``["ssh_1995-01.nc", "ssh_1995-02.nc"]`` gives
    ``"ssh_1995-0*.nc"``.

    Parameters
    ----------
    filenames : list of str
        Filenames to combine.

    Returns
    -------
    str
        Glob pattern containing at least one ``"*"``.

    Raises
    ------
    ValueError
        If the names share no wildcard-able pattern or differ in extension.
    """
    patterns = []
    for name, following in zip(filenames, filenames[1:]):
        matcher = difflib.SequenceMatcher(None, name, following)
        pattern = ""
        for block in matcher.get_matching_blocks():
            pattern = name_match(block, pattern, name)
        patterns.append(pattern)
    common_name = min(patterns, key=len)
    if "*" not in common_name:
        raise ValueError("Filenames do not match")
    if common_name[-1] == ".":
        raise ValueError("Filenames formats do not match")
    return common_name


def coordinate_names(dataset):
    """Sorted coordinate names of a dataset."""
    return sorted(dataset.coords.keys())


def variable_names(dataset):
    """Sorted names of the data variables of a dataset, coordinates excluded."""
    return sorted(str(name) for name in dataset.data_vars)
