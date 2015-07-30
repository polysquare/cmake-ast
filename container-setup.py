# /container-setup.py
#
# Initial setup script specific to cmake-ast. Passes through options to set
# up a python and cmake container. Interrogates the cmake installation to
# determine where the module files are and sets that in
# CMAKE_INSTALL_PATH so that cmake-ast doesn't need to
# determine that by itself.
#
# See /LICENCE.md for Copyright information
"""Initial setup script specific to cmake-ast."""

import os

import platform


def run(cont, util, shell, argv=None):
    """Set up language runtimes and pass control to python project script."""
    cont.fetch_and_import("setup/python/setup.py").run(cont,
                                                       util,
                                                       shell,
                                                       argv)
    cmake_cont = cont.fetch_and_import("setup/cmake/setup.py").run(cont,
                                                                   util,
                                                                   shell,
                                                                   argv)

    # Now that the cmake container is set up, use its execute method
    # to find out where cmake scripts are actually installed.
    #
    # The answer might be obvious from just using "which" on OS X and
    # Linux, but on Windows, the binaries are symlinked into another
    # directory - we need the true install location.
    with cont.in_temp_cache_dir():
        with open("cmroot.cmake", "w") as root_script:
            root_script.write("message (${CMAKE_ROOT})")

        install_path = bytearray()

        def steal_output(process, outputs):
            """Steal output from container executor."""
            install_path.extend(outputs[1].read().strip())
            return process.wait()

        cmake_cont.execute(cont,
                           steal_output,
                           "cmake",
                           "-P",
                           root_script.name)

        # If we're on linux, then the returned path is going to be
        # relative to the container, so make that explicit, since we're
        # not running the tests inside the container.
        if platform.system() == "Linux":
            root_fs_path_bytes = cmake_cont.root_fs_path()
            install_path = os.path.join(root_fs_path_bytes.decode("utf-8"),
                                        install_path.decode("utf-8")[1:])
            install_path = os.path.normpath(install_path)
        else:
            install_path = install_path.decode("utf-8")

        util.overwrite_environment_variable(shell,
                                            "CMAKE_INSTALL_PATH",
                                            install_path)
