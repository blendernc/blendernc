================
Simple animation
================

.. important::
    For this third example, it is important to be familiar with the simple UI of BlenderNC (:ref:`beginner_mode`).

Data provided
-------------



Download your own data! (optional)
----------------------------------

Let's download daily sea surface temperature data from 1981 to the present derived from satellite observations (`for more info click here <https://cds.climate.copernicus.eu/cdsapp#!/dataset/satellite-sea-surface-temperature?tab=overview>`__) and download it by following the instructions `here <https://cds.climate.copernicus.eu/cdsapp#!/dataset/satellite-sea-surface-temperature?tab=form>`__! Let's start downloading one year, for example, 2020.

.. code-block:: bash

    import cdsapi

    c = cdsapi.Client()

    c.retrieve(
    'satellite-sea-surface-temperature',
    {
    'variable': 'all',
    'format': 'tgz',
    'processinglevel': 'level_4',
    'sensor_on_satellite': 'combined_product',
    'version': '2_0',
    'year': [
    '2020',
    ],
    'month': [
    '01', '02', '03',
    '04', '05', '06',
    '07', '08', '09',
    '10', '11', '12',
    ],
    'day': [
    '01', '02', '03',
    '04', '05', '06',
    '07', '08', '09',
    '10', '11', '12',
    '13', '14', '15',
    '16', '17', '18',
    '19', '20', '21',
    '22', '23', '24',
    '25', '26', '27',
    '28', '29', '30',
    '31',
    ],
    },
    'download.tar.gz')

.. important::
    You will need to create an account and follow the instructions to use the ``cdsapp``: `click here <https://cds.climate.copernicus.eu/api-how-to>`__!

Load data!
----------

Open Blender (>2.83), in the 3D view, open the `sidebar` by pressing "n".

- Switch to the BlenderNC panel and click on ``Load netCDF``. Then click the folder icon, navigate and select the GEBCO bathymetry netCDF.

- Select variable (``elevation``):

- Let's increase the resolution to 100%:

- Click in the check box next to ``Animate netCDF``

- Now, we can apply the material BlenderNC just created, but first, lets delete the default cube (shortuct ``x``), create a sphere (shortcut ``shift + a`` - ``Mesh -> UV Sphere``), and scale it to ``2x`` (shortcut ``s + 2 + return``)

- Select sphere by clicking over it, then click apply material (highlighted in blue above).

There will be no visible change until we switch to a rendered 3D viewport (``Z`` and click over ) or render the camera (shortcut ``F12``).

Press ``0`` in your number path to change your view to the camera view. If you are using a laptop, you can emulate a number path by following the instructions in this `link <https://docs.blender.org/manual/en/latest/editors/preferences/input.html>`__!

Once you are in the camera mode, press ``Spacebar``on your keyboard to play the animation. Voila! now we have a netCDF animation.

.. [Dataset]
    Merchant, C.J., Embury, O., Bulgin, C.E., Block, T., Corlett, G.K., Fiedler, E., Good, S.A., Mittaz, J., Rayner, N.A., Berry, D., Eastwood, S., Taylor, M., Tsushima, Y., Waterfall, A., Wilson, R. and Donlon, C. (2019), Satellite-based time-series of sea-surface temperature since 1981 for climate applications. Scientific Data 6, 223, doi:10.1038/s41597-019-0236-x