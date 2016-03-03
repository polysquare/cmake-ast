# /test/test_print_smoke.py
#
# Smoke test cmakeast.print against every single file in the cmake
# distribution
#
# See /LICENCE.md for Copyright information
"""Smoke test cmake-print-ast."""

import os

import subprocess

import sys

import cmakeast

from nose_parameterized import parameterized

from six import StringIO

import testtools

if sys.version_info.major >= 3:
    import shutil
else:
    import shutilwhich as shutil


def _discover_cmake_module_path():
    """Determine cmake module path."""
    if os.environ.get("CMAKE_INSTALL_PATH"):
        cmake_module_path = os.environ["CMAKE_INSTALL_PATH"]
    else:
        path_to_cmake = shutil.which("cmake")

        if path_to_cmake is None:
            sys.stderr.write("cmake not found on this system")
            return None

        version_line = subprocess.check_output([path_to_cmake,
                                                "--version"]).decode("utf-8")

        version_numbers = version_line[len("cmake version "):].split(".")
        version_suffix = "-{0}.{1}".format(version_numbers[0],
                                           version_numbers[1])

        cmake_module_path = os.path.join(os.path.dirname(path_to_cmake),
                                         "../share/",
                                         "cmake{0}".format(version_suffix),
                                         "Modules")
        cmake_module_path = os.path.normpath(cmake_module_path)

    return cmake_module_path

CMAKE_MODULE_PATH = _discover_cmake_module_path()


# First find cmake and then find the module path
def _discover_test_files():
    """Discover a list of files to run smoke tests on.

    This is generally every file that came with the cmake distribution
    """
    # List of files we will be testing against
    test_files = []

    # These files are templates and invalid cmake code
    exclude_files = ["run_nvcc.cmake"]

    if CMAKE_MODULE_PATH:
        for path, dirs, files in os.walk(CMAKE_MODULE_PATH):
            del dirs
            for filename in files:
                if (not os.path.basename(filename) in exclude_files and
                        filename[-6:] == ".cmake"):
                    test_files.append(os.path.join(path, filename))

    return sorted(test_files)


def _format_filename_doc(func, num, params):
    """Format docstring for smoke tests."""
    del num

    prefix = len(CMAKE_MODULE_PATH) + 1
    return func.__doc__.format(params[0][0][prefix:])


# suppress(R0903,too-few-public-methods)
class TestPrintAST(testtools.TestCase):
    """Smoke tests for printing the AST."""

    # pylint can get confused if we don't have an up-to-date
    # version of nose-parameterized installed.
    #
    # suppress(unexpected-keyword-arg)
    @parameterized.expand(_discover_test_files(),
                          testcase_func_doc=_format_filename_doc)
    def test_smoke(self, filename):
        """Run printer against {}."""
        self.patch(sys, "stdout", StringIO())

        cmakeast.printer.do_print(filename)
        self.assertTrue(True)
