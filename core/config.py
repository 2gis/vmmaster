import imp
import inspect
import os


def full_path(path_to_config):
    if path_to_config.startswith(os.sep):
        return path_to_config
    else:
        curframe = inspect.currentframe()
        outerframes = inspect.getouterframes(curframe)
        calpath = None
        for (frame, filename, line_number,
             function_name, lines, index) in outerframes:
            if filename != __file__:
                calpath = filename
                break
        path_to_config = os.sep.join([
            os.path.dirname(calpath), path_to_config
        ])
    return path_to_config


def _import(filename):
    (path, name) = os.path.split(filename)
    (name, ext) = os.path.splitext(name)

    (fp, filename, data) = imp.find_module(name, [path])
    try:
        return imp.load_module(name, fp, filename, data)
    finally:
        # Since we may exit via an exception, close fp explicitly.
        if fp:
            fp.close()


def create_if_not_exist(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)


class Config(object):
    def update(self, new_values):
        self.__dict__.update(new_values)

        create_if_not_exist(self.ORIGINS_DIR)
        create_if_not_exist(self.CLONES_DIR)
        create_if_not_exist(self.LOG_DIR)
        create_if_not_exist(self.SCREENSHOTS_DIR)


def setup_config(path_to_config):
    temp_config = _import(full_path(path_to_config))
    global config
    config.update(temp_config.Config.__dict__)


config = Config()
