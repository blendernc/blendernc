.. blendernc documentation master file, created by
   sphinx-quickstart on Sun May 31 19:41:12 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to BlenderNC's documentation!
=====================================

=========
BlenderNC
=========

**BlenderNC** is a Blender add-on that allows importing datacubes into
Blender (i.e. netCDF, cfGrib, and zarr files). It allows 2D and 3D visualization and the generation of scientific data
animations. The main development of *BlenderNC* currently focuses on
geo-spatial data (i.e. Oceanographic - Atmospheric data), however, the framework
should support the load of any datacube.

.. image:: ../images/GEBCO_blendernc.png
  :width: 100%
  :alt: GEBCO Bathymetry (5400x2700 pixels)

.. toctree::
   :maxdepth: 2
   :caption: Quick Start

   install
   howtouse
   preferences
   remote_render

.. toctree::
   :maxdepth: 2
   :caption: Dive in!


.. toctree::
   :maxdepth: 1
   :caption: Examples

   examples/import_gebco_netCDF
   examples/simple_animation
   examples/import_ECMWF_netCDF
   examples/node_tree_editor
   examples/import_ECMWF_grib
   examples/displacement_animation
   examples/multiple_field_animations
   examples/irregular_grid
   examples/headless_blendernc_simple_animation

.. toctree::
   :maxdepth: 1
   :caption: API Reference

   modules/blendernc

.. toctree::
   :caption: Help & References

   help
   contribute


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

Support
=======

**BlenderNC** is supported by:

.. image:: ../images/logo_ESoWC.png
   :target: https://esowc.ecmwf.int/
   :alt: ESoWC logo
   :width: 47%


.. image:: ../images/logo_cosima.png
   :target: http://cosima.org.au/
   :class: float-right
   :alt: COSIMA logo
   :width: 47%


- **BlenderNC** is part of the `ECMWF Summer of Weather Code 2021 <https://esowc.ecmwf.int/>`_, an innovation program organised by the `European Centre for Medium-Range Weather Forecasts <https://www.ecmwf.int>`_ focusing on weather- and climate-related open-source developments. The sponsored work aims to implement and improve support of weather and climate data visualizations in GRIB format within **BlenderNC**.

.. image:: ../images/esowc_2021_banner.jpg
   :width: 400
   :align: center
   :target: https://esowc.ecmwf.int
   :alt: ESoWC logo

- `Consortium for Ocean-Sea Ice Modelling in Australia <http://cosima.org.au/>`_ (COSIMA) funds development of **BlenderNC** to visualize numerical models of the global ocean and sea ice (`ACCESS-OM2 <http://cosima.org.au/index.php/models/access-om2/>`_).

Community
=========

This section show animations submitted by the BlenderNC users.

.. image:: ../images/example_PT_city.gif
   :width: 100%
   :alt: Potential temperature.

The animation by `JoshuaB-L
<https://github.com/JoshuaB-L>`_ shows equivalent potential temperature (theta-e) of the adiabatic process - air moving across a warming urban surface from 10:00-11:00 am on 16-07-2018 at Potsdamer Platz, Berlin. The wind speed is 7.2 km/h considered a factor of 2 on the Beaufort Scale (‘Light breeze’). The temperature scale is shown in Kelvins (i.e. 20.85 °C - 28.65 °C range). Convection of the rising air parcels is clearly visible from the ground and building surfaces. Heat transfer occurs due to the mixing of warm air (at ground level z0) and cool air (above the building canopy) caused by the turbulent rising eddies. Thus, the ambient air temperature of the urban environment rises. The simulation model used is PALM in LES mode. More information can be found `here <https://palm.muk.uni-hannover.de/trac/wiki/doc/tut/palm>`_.

