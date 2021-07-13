.. _download_more_data:

===================
Download more data!
===================


ECMWF
-----

Let's download daily sea surface temperature data from 1981 to the present derived from satellite observations (`for more info click here <https://cds.climate.copernicus.eu/cdsapp#!/dataset/satellite-sea-surface-temperature?tab=overview>`__) and download it by following the instructions `here <https://cds.climate.copernicus.eu/cdsapp#!/dataset/satellite-sea-surface-temperature?tab=form>`_! Let's start downloading one year, for example, 2020.

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

.. [Dataset]
    Merchant, C.J., Embury, O., Bulgin, C.E., Block, T., Corlett, G.K., Fiedler, E., Good, S.A., Mittaz, J., Rayner, N.A., Berry, D., Eastwood, S., Taylor, M., Tsushima, Y., Waterfall, A., Wilson, R. and Donlon, C. (2019), Satellite-based time-series of sea-surface temperature since 1981 for climate applications. Scientific Data 6, 223, doi:10.1038/s41597-019-0236-x


COSIMA
------