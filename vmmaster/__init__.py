import os
from ._version import get_versions


def package_dir():
    return os.path.dirname(__file__) + os.sep

__version__ = get_versions()['version']
del get_versions
