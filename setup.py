# /setup.py
#
# Installation and setup script for cmakeast
#
# See LICENCE.md for Copyright information
"""Installation and setup script for cmakeast"""

from setuptools import setup, find_packages

setup(name="cmakeast",
      version="0.0.8",
      description="CMake AST",
      long_description="Reduce a CMake file to an abstract syntax tree",
      author="Sam Spilsbury",
      author_email="smspillaz@gmail.com",
      classifiers=["Development Status :: 3 - Alpha",
                   "Intended Audience :: Developers",
                   "Topic :: Software Development :: Build Tools",
                   "License :: OSI Approved :: MIT License",
                   "Programming Language :: Python :: 3"],
      url="http://github.com/polysquare/cmake-ast",
      license="MIT",
      keywords="development ast cmake",
      packages=find_packages(exclude=["tests"]),
      install_requires=["setuptools"],
      extras_require={
          "test": ["coverage",
                   "testtools",
                   "shutilwhich",
                   "nose",
                   "nose-parameterized",
                   "mock"]
      },
      entry_points={
          "console_scripts": [
              "cmake-print-ast=cmakeast.printer:main"
          ]
      },
      test_suite="nose.collector")
