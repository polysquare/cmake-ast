# /setup.py
#
# Installation and setup script for cmakeast
#
# See /LICENCE.md for Copyright information
"""Installation and setup script for cmakeast."""

from setuptools import find_packages, setup

setup(name="cmakeast",
      version="0.0.17",
      description="""Parse a CMake file into an Abstract Syntax Tree.""",
      long_description_markdown_filename="README.md",
      author="Sam Spilsbury",
      author_email="smspillaz@gmail.com",
      classifiers=["Development Status :: 3 - Alpha",
                   "Programming Language :: Python :: 2",
                   "Programming Language :: Python :: 2.7",
                   "Programming Language :: Python :: 3",
                   "Programming Language :: Python :: 3.1",
                   "Programming Language :: Python :: 3.2",
                   "Programming Language :: Python :: 3.3",
                   "Programming Language :: Python :: 3.4",
                   "Intended Audience :: Developers",
                   "Topic :: Software Development :: Build Tools",
                   "License :: OSI Approved :: MIT License"],
      url="http://github.com/polysquare/cmake-ast",
      license="MIT",
      keywords="development ast cmake",
      packages=find_packages(exclude=["test"]),
      install_requires=["setuptools"],
      extras_require={
          "upload": ["setuptools-markdown"]
      },
      entry_points={
          "console_scripts": [
              "cmake-print-ast=cmakeast.printer:main"
          ]
      },
      test_suite="nose.collector",
      zip_safe=True,
      include_package_data=True)
