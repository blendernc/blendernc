==========
Contribute
==========

Contributions are welcome: bug reports, ideas, documentation and code. To
report a problem or suggest a feature, open an issue at
`BlenderNC issues <https://github.com/blendernc/blendernc/issues>`_. To
contribute code, open a pull request against the ``master`` branch of the
`BlenderNC repository <https://github.com/blendernc/blendernc>`_.

Development setup
#################

The suggested setup uses Visual Studio Code, which can start Blender with
your local copy of BlenderNC loaded as an extension.

|vscode badge|

.. |vscode badge| image:: https://img.shields.io/static/v1?logo=visualstudiocode&label=&message=Open%20in%20Visual%20Studio%20Code&labelColor=2c2c32&color=007acc&logoColor=007acc
   :target: https://open.vscode.dev/blendernc/blendernc

1. Install `Visual Studio Code <https://code.visualstudio.com/>`_ and its
   `Blender Development` extension (``jacqueslucke.blender-development``).
2. Fork the repository on GitHub, then clone it:

   .. code-block:: bash

       git clone https://github.com/<your-user>/blendernc.git
       cd blendernc
       git remote add upstream https://github.com/blendernc/blendernc.git

3. Open the cloned folder in Visual Studio Code.
4. Press ``Ctrl+Shift+P`` (``Cmd+Shift+P`` on macOS), run ``Blender: Start``
   and choose your Blender 5.2 executable.

Blender now runs with BlenderNC loaded from your clone. Run
``Blender: Reload Addons`` after changing the code.

Dependencies
------------

Blender installs the Python libraries BlenderNC needs from the wheels listed
in ``blender_manifest.toml``. Dependencies are managed with
`Poetry <https://python-poetry.org>`_ in ``pyproject.toml``. After changing
them, update the wheels and the manifest from the repository root:

.. code-block:: bash

    poetry lock
    python update_wheels.py

Log file
--------

BlenderNC writes its messages to ``log.txt`` in the extension's user
directory. :func:`blendernc.log_path` returns its location. When BlenderNC is
loaded through Visual Studio Code, import it under the development name:

.. code-block:: python

    import bl_ext.vscode_development.blendernc as blendernc
    print(blendernc.log_path())

Code conventions
################

- **Reporting errors.** Don't raise exceptions from operators, nodes or
  property callbacks: the user never sees the traceback. Use
  ``report_error`` or the ``report_errors`` decorator from
  ``blendernc/messages.py``, which show the message in Blender, write it to
  the log and return ``{"CANCELLED"}``. Helper functions may raise
  ``ValueError``; the operator calling them turns it into a report.
- **Small functions.** flake8 rejects functions with a complexity above 5.
  Split long functions into small helpers.
- **Docstrings.** Use the `numpydoc <https://numpydoc.readthedocs.io/>`_
  style, so the API reference is generated from the code.

Testing
#######

Tests live in ``tests/`` as ``*.test.py`` files. Each file runs inside
Blender in background mode. A pull request is only merged when all tests
pass.

Run one test file
-----------------

From the ``tests/`` folder, with ``blender`` pointing to your Blender 5.2
executable:

.. code-block:: bash

    PYTHONPATH=/path/to/blendernc blender --addons blendernc -E CYCLES -b \
        --python-use-system-env --python ui_panel.test.py

Check the ``Ran N tests`` and ``OK`` / ``FAILED`` lines of the output.

Run all tests
-------------

``tests/run_tests.py`` runs every ``*.test.py`` file and fails if any of
them fails:

.. code-block:: bash

    cd tests
    python run_tests.py /path/to/blender test

Run the tests like the CI
-------------------------

The CI runs the tests in the
`ranchcomputing Blender CPU image <https://github.com/ranchcomputing/blender-cpu-image>`_
with ``tests/build-test.sh``, which also measures coverage. To do the same,
run this from the repository root:

.. code-block:: bash

    docker pull ghcr.io/ranchcomputing/blender-cpu-image:5.2.0
    docker run -w /blendernc --rm \
        --mount type=bind,source="$(pwd)",target=/blendernc \
        -t ghcr.io/ranchcomputing/blender-cpu-image:5.2.0 \
        /bin/sh -c "bash ./tests/build-test.sh"

``tests/docker_test.sh`` wraps the same command.

.. important::
    ``source="$(pwd)"`` mounts the current folder into the container. Run the
    command from the root of the cloned repository, the folder that contains
    ``pyproject.toml``.

Linting and commits
###################

`pre-commit <https://pre-commit.com/>`_ checks the code before each commit
with:

- `Black <https://github.com/psf/black>`_ (formatting, 88 columns),
- `isort <https://pycqa.github.io/isort/>`_ (import order, Black profile),
- `Flake8 <https://flake8.pycqa.org/>`_ (style and complexity; ``tests/`` is
  excluded),
- `commitlint <https://commitlint.js.org/>`_ and
  `Commitizen <https://commitizen-tools.github.io/commitizen/>`_ (commit
  messages).

Install the hooks once:

.. code-block:: bash

    pip install pre-commit
    pre-commit install
    pre-commit install --hook-type commit-msg

To check every file before opening a pull request:

.. code-block:: bash

    pre-commit run --all-files

Commit messages follow
`Conventional Commits <https://www.conventionalcommits.org/>`_, for example
``feat: add colormap node``, ``fix: keep material after rebake`` or
``docs: simplify quickstart``. Releases are versioned from these prefixes, so
use them consistently.

Documentation
#############

The documentation is written in reStructuredText in ``docs/source`` and built
with `Sphinx <https://www.sphinx-doc.org/>`_. To build it locally:

.. code-block:: bash

    pip install -r docs/requirements.txt
    cd docs
    make html

Open ``docs/build/html/index.html`` to see the result.

Continuous integration
######################

GitHub Actions run these checks:

- **Tests** run on every push and pull request, and coverage is uploaded to
  Codecov.
- **Black, Flake8 and commitlint** check pull requests and pushes.
- **Zip release.** Pushes to ``master``, ``dev`` or ``distribution`` publish
  a zip of the add-on to
  `blendernc-zip-install <https://github.com/blendernc/blendernc-zip-install>`_,
  which users can install in Blender (see
  `ci.yml <https://github.com/blendernc/blendernc/blob/master/.github/workflows/ci.yml>`_).
- **Release.** Pushes to ``master`` run
  `python-semantic-release <https://python-semantic-release.readthedocs.io/>`_,
  which picks the next version from the commit messages, writes the release
  notes and publishes the package to `PyPI <https://pypi.org/project/blendernc/>`_
  (see
  `release.yml <https://github.com/blendernc/blendernc/blob/master/.github/workflows/release.yml>`_).
