======
Report
======

**BlenderNC** is currently under development, and we appreciate any input! If you have any issue, utility to implement, or comment, please submit and report them at: `BlenderNC issues <https://github.com/josuemtzmo/blendernc/issues>`_.

===========
Development
===========

If you want to contribute to the development of BlenderNC, please submit a pull request to the `master branch or dev branch <https://github.com/josuemtzmo/blendernc/pulls>`_.

Development workflow
####################

- Download and install `Visual Studio Code <https://code.visualstudio.com/>`_.
- Install Visual Studio Code Add-On ``jacqueslucke.blender-development`` by searching at the `Extensions in Marketplace`.
- Set up your ``Blender`` executable by pressing ``ctrl+shift+P`` -> ``Blender Start`` -> ``Choose new blender executable``.
- Clone BlenderNC source code (`BlenderNC repo <https://github.com/blendernc/blendernc>`_):

    .. code-block::

        git clone https://github.com/blendernc/blendernc.git

- Set up your remotes (i.e. ``origin`` and ``upstream``).
- Initiate a new workspace in the cloned folder.
- Voalà! Now you can develop, debug, and modify **BlenderNC**.

Testing
#######

In order to merge into any branch of the **BlenderNC** repository, all test must pass. Locally testing **BlenderNC** is really simple, as it uses docker containers by `nytimes/rd-blender-docker <https://github.com/nytimes/rd-blender-docker>`_. Execute the following code from the cloned repository root directory:

.. code-block::

    docker pull nytimes/blender:latest
    docker run -w /addon/blendernc -it --rm --mount type=bind,source="$(pwd)",target=/addon/blendernc -t nytimes/blender:latest /bin/sh -c

If you want more control on each test, you can run an interactive docker container:

.. code-block::

    docker pull nytimes/blender:latest
    docker run -w /addon/blendernc --rm -it --mount type=bind,source="$(pwd)",target=/addon/blendernc -t nytimes/blender:latest /bin/bash

and then run the following code in sections:

.. code-block::

    #!/bin/sh

    $BLENDERPY -m ensurepip --default-pip

    $BLENDERPY -m pip install -r requirements.txt --progress-bar off

    $BLENDERPY -m pip install coverage --progress-bar off

    $BLENDERPY -m pip install -e . --progress-bar off

    COVERAGE_PROCESS_START=${PWD}"/.coveragerc"
    export COVERAGE_PROCESS_START=$COVERAGE_PROCESS_START
    export PYTHONPATH=$PYTHONPATH:${PWD}

    cd tests

    echo -e "import coverage \n\ncov=coverage.process_startup()\n"> sitecustomize.py
    echo -e "print('Initiate coverage')" >> sitecustomize.py
    echo -e "print(cov)" >> sitecustomize.py

    export PYTHONPATH=$PYTHONPATH:${PWD}

    $BLENDERPY run_tests.py

    coverage combine
    coverage report
    coverage xml

.. important::
    Note the flag ``--mount type=bind,source="$(pwd)"`` when using the ``docker run`` command. The source path will be the current working directory. Make sure it corresponds to the root of the cloned repository (i.e. ``/parent/path/to/blendernc/blendernc``, where ``/parent/path/to/blendernc`` is the parent directory where ``github clone`` created the repository.

================
Related Projects
================

The netCDFs used for the examples and figures come from a high-resolution ocean and ice model of the COSIMA community models (e.g. MOM5). These models are
run on `NCI Gadi <https://nci.org.au>`_.


Underlying Python technologies
------------------------------

- `Dask <https://dask.org>`_

- `xarray <http://xarray.pydata.org/en/stable/#>`_

