"""Jobcu: a private job search app that runs on your own computer."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("jobcu")
except PackageNotFoundError:  # running from a plain source folder
    __version__ = "0.0.0"

COPYRIGHT = "© Utku Deniz Altiok. All rights reserved."
