# /tests/print_smoke_test.py
#
# Smoke test cmakeast.print against every single file in the cmake
# distribution
#
# See LICENCE.md for Copyright information
"""Smoke test cmake-print-ast."""

import os

import subprocess

import sys

import cmakeast

from nose_parameterized import parameterized

import testtools

if sys.version_info.major >= 3:
    import shutil
else:
    import shutilwhich as shutil


# First find cmake and then find the module path
def _discover_test_files():
    """Discover a list of files to run smoke tests on.

    This is generally every file that came with the cmake distribution
    """
    path_to_cmake = shutil.which("cmake")
    if path_to_cmake is None:
        sys.stderr.write("cmake not found on this system")
        sys.exit(0)

    version_line = subprocess.check_output([path_to_cmake,
                                            "--version"]).decode("utf-8")

    version_numbers = version_line[len("cmake version "):].split(".")
    module_version_suffix = "-{0}.{1}".format(version_numbers[0],
                                              version_numbers[1])

    cmake_module_path = os.path.join(os.path.dirname(path_to_cmake),
                                     "../share/",
                                     "cmake{0}".format(module_version_suffix),
                                     "Modules")
    cmake_module_path = os.path.normpath(cmake_module_path)

    # These files are templates and invalid cmake code
    exclude_files = ["run_nvcc.cmake"]

    # List of files we will be testing against
    test_files = []

    for path, dirs, files in os.walk(cmake_module_path):
        del dirs
        for filename in files:
            if not os.path.basename(filename) in exclude_files and\
               filename[-6:] == ".cmake":
                test_files.append(os.path.join(path, filename))

    return test_files


class TestPrintAST(testtools.TestCase):  # pylint:disable=R0903

    """Smoke tests for printing the AST."""

    @parameterized.expand(_discover_test_files())
    def test_smoke(self, filename):
        """Run printer against {0}.""".format(filename)
        cmakeast.printer.do_print(filename)
        self.assertTrue(True)
