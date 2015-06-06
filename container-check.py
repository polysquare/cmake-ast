# /container-check.py
#
# This is a wrapper around check/python/check.py which containerizes executes
# that script in an OS container. This allows us to find the correct path
# to the installed cmake modules.
#
# See /LICENCE.md for Copyright information

import os


def run(cont, util, shell, argv=None):
    """Run check/python/check.py in a container."""
    config_os_container = "setup/project/configure_os.py"
    os_cont = cont.fetch_and_import(config_os_container).get(cont,
                                                             util,
                                                             shell,
                                                             None)

    os_cont.execute(cont,
                    util.running_output,
                    "python",
                    cont.script_path("bootstrap.py").fs_path,
                    "-d",
                    cont.path(),
                    "-s",
                    "check/python/check.py",
                    *argv)

    return cont.return_code()
