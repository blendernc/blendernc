# BlenderNC

![Read the Docs](https://img.shields.io/readthedocs/blendernc) ![Github CI](https://github.com/blendernc/blendernc/actions/workflows/test.yml/badge.svg) [![codecov](https://codecov.io/gh/blendernc/blendernc/branch/master/graph/badge.svg?token=NYJMMGIMPJ)](https://codecov.io/gh/blendernc/blendernc) [![Maintainability](https://api.codeclimate.com/v1/badges/bbd6f981e5f5a26c6a56/maintainability)](https://codeclimate.com/github/blendernc/blendernc/maintainability) [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) ![GitHub](https://img.shields.io/github/license/blendernc/blendernc?color=lightblue) ![blender support](https://img.shields.io/badge/blender-5.2+-blueviolet) ![GitHub release (latest by date)](https://img.shields.io/github/v/release/blendernc/blendernc?label=tag) [![pre-commit.ci status](https://results.pre-commit.ci/badge/github/blendernc/blendernc/master.svg)](https://results.pre-commit.ci/latest/github/blendernc/blendernc/master) [![semantic-release](https://img.shields.io/badge/%20%20%F0%9F%93%A6%F0%9F%9A%80-semantic--release-e10079.svg)](https://github.com/python-semantic-release/python-semantic-release)


**BlenderNC** is an open source add-on and Python module to visualize **netCDF**, **grib**, and **zarr** datasets in [**Blender**](https://www.blender.org).

BlenderNC builds upon [**xarray**](https://github.com/pydata/xarray) and [**dask**](https://dask.org) to lazy load, manipulate, and display datasets as images in Blender.

#### Why BlenderNC?

Science visualization is a fundamental part of science communication and the exploration of large datasets. However, production quality real-time visualization and animation of scientific data has remained unreachable to the scientific community. BlenderNC main goal is to facilitate the generation of quality animations of scientific gridded data with a powerful and simple interface. For example:

- Quick load of datasets:

<img src="https://raw.githubusercontent.com/blendernc/blendernc/master/docs/videos/quick_load_gif.gif" width="70%" />

- Nodes tree for more complex visualizations, for example:

  - the Earth's topograhy

  <img src="https://raw.githubusercontent.com/blendernc/blendernc/master/docs/images/GEBCO_blendernc.png" width="70%" />

  - Or even a 4D visualization of an ocean eddy interacting with sea-ice:

  <img src="https://raw.githubusercontent.com/blendernc/blendernc/master/docs/videos/eddy_50p_ice.gif" width="70%" />

Installation
------------

1. Download the zip for your operating system from the [latest release](https://github.com/blendernc/blendernc/releases/latest):
   - **Windows (64-bit):** `blendernc-<version>-windows_x64.zip`
   - **macOS (Apple Silicon, macOS 15 or newer):** `blendernc-<version>-macos_arm64.zip`
   - **Linux (64-bit):** `blendernc-<version>-linux_x64.zip`

   Each zip bundles the Python libraries BlenderNC needs for that platform, so pick the one that matches your system.
2. Drag and drop the zip into Blender, or go to `Edit > Preferences > Get Extensions`, open the drop-down menu in the top-right corner, choose `Install from Disk...` and select the zip.
3. Make sure BlenderNC is enabled in `Edit > Preferences > Add-ons`.

See the [installation guide](https://blendernc.readthedocs.io/en/latest/install.html) for more details.

Documentation
-------------

Learn more about BlenderNC in the official documentation at [https://blendernc.readthedocs.io](https://blendernc.readthedocs.io)

Contributing
------------

All contributions, bug reports, bug fixes, documentation improvements, enhancements, and ideas are welcome. More information about contributing to BlenderNC can be found at our [Contribution page](https://blendernc.readthedocs.io/en/latest/contribute.html).

Use Github to:
- report bugs,
- suggest features,
- provide examples,
- and view the source code.

Support
-------

**BlenderNC** is supported by:

<div style="width:100%">
<a href="https://esowc.ecmwf.int">
<img src="https://raw.githubusercontent.com/blendernc/blendernc/master/docs/images/logo_ESoWC.png" width="47%" style='margin-bottom:5px' />
</a>
<a href="http://cosima.org.au/">
<img src="https://raw.githubusercontent.com/blendernc/blendernc/master/docs/images/logo_cosima.png" width="47%" style='float:right;'/>
</a>
</div>

To implement and improve support of weather and climate data visualizations in GRIB format and visualize numerical models of the global ocean and sea-ice.