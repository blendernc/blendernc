.. _remote_render:

==================================
Remote and containerised rendering
==================================

Once a visualisation runs from the terminal (see :ref:`terminal_guide`), it
runs anywhere Blender runs: a workstation reached over SSH, a Docker
container, or a cluster node. This page gives working examples for each,
built on the same container image that the project's continuous integration
uses to test every commit.

.. important::
   The examples target Blender 5.2 and the CPU. EEVEE and GPU rendering need
   a display or a configured GPU in the container and are not covered here.


Remote machine over SSH
=======================

Install BlenderNC on the remote machine with the extension command line and
run the script there; only the data and the results travel over the network.

.. code-block:: bash

   # Copy the data and the script
   rsync -av data/ssh_1995-01.nc render_datacube.py server:~/work/

   # Render on the server (nohup keeps it running if the connection drops)
   ssh server 'cd ~/work && nohup blender -b --python-exit-code 1 \
       --python render_datacube.py -- ssh_1995-01.nc adt out/ssh.png --step 4 \
       > render.log 2>&1 &'

   # Fetch the result
   rsync -av server:~/work/out/ renders/

If the remote machine has no graphical session, install the extension with
``blender --command extension install-file`` as described in the terminal
guide, or load the add-on from a checkout with ``PYTHONPATH`` and
``--addons blendernc``.


Docker
======

The image used by CI
--------------------

The test workflow in ``.github/workflows/test.yml`` runs on
``ghcr.io/ranchcomputing/blender-cpu-image:5.2.0``. It contains a CPU build
of Blender and a system Python with the same version as Blender's (3.13),
which is why the add-on can be loaded with ``--python-use-system-env``. The
repository is mounted at ``/blendernc`` and that path is the working
directory:

.. code-block:: bash

   docker pull ghcr.io/ranchcomputing/blender-cpu-image:5.2.0

   docker run --rm -w /blendernc \
       --mount type=bind,source="$(pwd)",target=/blendernc \
       -t ghcr.io/ranchcomputing/blender-cpu-image:5.2.0 \
       /bin/sh -c "bash ./tests/build-test.sh"

``tests/build-test.sh`` is the whole CI test job in one script. It

1. installs ``pip`` and ``coverage`` into the container's Python,
2. runs the tests that need no scientific libraries,
3. installs ``requirements.txt``,
4. runs every ``tests/*.test.py`` through ``tests/run_tests.py`` with
   ``blender --addons blendernc -b --python-use-system-env``, and
5. combines the coverage data into ``tests/.coverage_<blender version>``.

``tests/docker_test.sh`` wraps the same ``docker run`` line with a prompt per
Blender version, so the CI job can be reproduced locally with:

.. code-block:: bash

   bash tests/docker_test.sh

Rendering inside the container
------------------------------

The same image renders a datacube. The only additions are a second mount for
the output and the ``pip install`` of the requirements, because the base
image does not ship them:

.. code-block:: bash

   mkdir -p renders
   docker run --rm -w /blendernc \
       --mount type=bind,source="$(pwd)",target=/blendernc \
       --mount type=bind,source="$(pwd)/renders",target=/out \
       ghcr.io/ranchcomputing/blender-cpu-image:5.2.0 /bin/sh -c '
           python -m ensurepip --default-pip
           python -m pip install -q -r requirements.txt
           export PYTHONPATH=/blendernc
           blender -b --python-exit-code 1 --addons blendernc --python-use-system-env \
               --python docs/source/scripts/render_datacube.py -- \
               tests/dataset/ssh_1995-01.nc adt /out/ssh.png --step 4 --frame 0
       '

The first run downloads the dependencies, after which the render itself
takes a few seconds. ``renders/ssh.png`` appears on the host because
``/out`` is a bind mount.

A reusable image
----------------

Installing the requirements on every run is slow. Bake them into a derived
image once:

.. code-block:: docker

   FROM ghcr.io/ranchcomputing/blender-cpu-image:5.2.0
   COPY requirements.txt /tmp/requirements.txt
   RUN python -m ensurepip --default-pip \
       && python -m pip install --no-cache-dir -r /tmp/requirements.txt
   WORKDIR /blendernc
   ENV PYTHONPATH=/blendernc

.. code-block:: bash

   docker build -t blendernc-render:5.2.0 .

   docker run --rm \
       --mount type=bind,source="$(pwd)",target=/blendernc \
       --mount type=bind,source="$(pwd)/renders",target=/out \
       blendernc-render:5.2.0 \
       blender -b --python-exit-code 1 --addons blendernc --python-use-system-env \
           --python docs/source/scripts/render_datacube.py -- \
           tests/dataset/ssh_1995-01.nc adt /out/ssh_ --step 4 --animate

Rendering many files is then a shell loop over the ``docker run`` line, or a
single Python script that iterates inside one container.


HPC clusters
============

Most clusters do not allow Docker but do provide Apptainer (formerly
Singularity), which can run the same image. Build the reusable image above
on a machine where you have Docker, push it to a registry you can reach from
the cluster, and pull it as a SIF file:

.. code-block:: bash

   apptainer pull blendernc.sif docker://<registry>/blendernc-render:5.2.0

   apptainer exec --bind "$PWD":/blendernc,"$PWD/renders":/out blendernc.sif \
       blender -b --python-exit-code 1 --addons blendernc --python-use-system-env \
           --python docs/source/scripts/render_datacube.py -- \
           /blendernc/data/ssh_1995-01.nc adt /out/ssh_ --step 2 --animate

A SIF image is read-only, so install the Python requirements in the Docker
build step rather than at run time. A minimal batch job for a Slurm scheduler
looks like:

.. code-block:: bash

   #!/bin/bash
   #SBATCH --job-name=blendernc
   #SBATCH --cpus-per-task=16
   #SBATCH --mem=32G
   #SBATCH --time=01:00:00

   cd "$SLURM_SUBMIT_DIR"
   mkdir -p renders
   apptainer exec --bind "$PWD":/blendernc,"$PWD/renders":/out blendernc.sif \
       blender -b --python-exit-code 1 --addons blendernc --python-use-system-env \
           --python docs/source/scripts/render_datacube.py -- \
           /blendernc/data/ssh_1995-01.nc adt /out/ssh_ --step 2 --animate

Set the frame range per job, or split the time axis across an array job, to
spread an animation over several nodes. Cycles uses all CPUs it is given;
match ``--cpus-per-task`` to the node size.

.. note::
   The Docker examples on this page were run on Blender 5.2.0 with the CI
   image. The Apptainer and Slurm snippets follow the same commands but were
   not executed on a cluster for this release; adapt the scheduler directives
   to your site.
