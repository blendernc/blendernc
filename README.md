# BlenderNC

|  Read the Docs |  Maintainability | CI Travis | Coverage | PyPi | Code Style |
|:--------------:|:----------------:|:---------:|:--------:|:----:|:----------:|
| [![Documentation Status](https://readthedocs.org/projects/blendernc/badge/?version=latest)](https://blendernc.readthedocs.io/en/latest/?badge=latest) | [![Maintainability](https://api.codeclimate.com/v1/badges/bbd6f981e5f5a26c6a56/maintainability)](https://codeclimate.com/github/blendernc/blendernc/maintainability) | [![Build Status](https://travis-ci.com/blendernc/blendernc.svg?branch=master)](https://travis-ci.com/blendernc/blendernc) | [![Project Status: Concept – Minimal or no implementation has been done yet, or the repository is only intended to be a limited example, demo, or proof-of-concept.](https://www.repostatus.org/badges/latest/concept.svg)](https://www.repostatus.org/#concept) | [![Project Status: WIP – Initial development is in progress, but there has not yet been a stable, usable release suitable for the public.](https://www.repostatus.org/badges/latest/wip.svg)](https://www.repostatus.org/#wip) | [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)|

**BlenderNC** is an open source add-on and Python module to visualize **netCDF** data in [**Blender**](www.blender.org). 

BlenderNC builds upon [**xarray**](https://github.com/pydata/xarray) and [**dask**](https://dask.org) to lazy load, manipulate, and display netCDF data files as images and volumetric data in Blender.

#### Why BlenderNC?

Science visualization is a fundamental part of science communication and exploration of large datasets. However, production quality real-time visualization and animation of scientific data has remain unreachable to the scientific community. BlenderNC main goal is to facilitate generation of quality animations of scientific gridded data with a powerful and simple interface. For example:

- Quick load of netCDFs:
<img src="./docs/images/quick_load_gif.gif" width="70%" />
- Nodes tree for more complex visualizations: 
<img src="./docs/images/GEBCO_blendernc.png" width="70%" />
- Math computations in BlenderNC node tree.

Documentation
------------- 

Lear more about BlenderNC in the official documentation at [https://blendernc.readthedocs.io](https://blendernc.readthedocs.io)

Contributing
------------
All contributions, bug reports, bug fixes, documentation improvements, enhancements, and ideas are welcome. More information about contributing to BlenderNC can be found at our [Contribution page](https://blendernc.readthedocs.io/contribute). 

Use Github to:
- report bugs,
- suggest features,
- provide examples,
- and view the source code. 