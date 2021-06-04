#!/usr/bin/env python3
from distutils.extension import Extension

import numpy as np

# TODO: Fix issue with blender not having python headers.
# from Cython.Build import cythonize
# from Cython.Distutils import build_ext
from setuptools import setup

extensions = Extension(
    name="cython_build.lic_internal",
    sources=["./blendernc/core/lic/lic_internal.pyx"],
)

setup(
    name="blendernc",
    version="0.1.0",
    description="Blender add-on to import netCDF",
    url="https://github.com/blendernc/blendernc",
    author="josuemtzmo",
    author_email="josue.martinezmoreno@anu.edu.au",
    license="MIT License",
    packages=[],
    install_requires=[],
    zip_safe=True,
    include_dirs=[np.get_include()],
    # cmdclass={"build_ext": build_ext},
    # TODO: Fix issue with blender not having python headers.
    # ext_modules=cythonize([extensions], build_dir="cython_build"),
)
