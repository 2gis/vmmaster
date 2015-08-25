import runpy
import imp
import inspect
import os


class Config(object):
    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, 'instance'):
            cls.instance = super(Config, cls).__new__(cls)
        return cls.instance

    def update(self, new_values):
        self.__dict__.update(new_values)

config = Config()


def setup_config(path_to_config):
    if path_to_config.startswith(os.sep):
        pass
    else:
        curframe = inspect.currentframe()
        calframe = inspect.getouterframes(curframe, 2)
        calpath = calframe[1][1]
        path_to_config = os.path.dirname(calpath) + os.sep + path_to_config
    attrs = runpy.run_path(path_to_config)
    temp_config = imp.new_module("temp_config")
    temp_config.__dict__.update(attrs)
    global config
    config.update(temp_config.Config.__dict__)
