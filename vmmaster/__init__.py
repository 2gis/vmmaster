import os


def package_dir():
    return os.path.dirname(__file__) + os.sep
from ._version import get_versions
__version__ = get_versions()['version']
del get_versions
