class ConfigInstance(object):
    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, 'instance'):
             cls.instance = super(ConfigInstance, cls).__new__(cls)
        return cls.instance

config = ConfigInstance()


def setup_config(path_to_config):
    config = ConfigInstance()
    execfile(path_to_config, globals())
    config.__dict__ = Config.__dict__.copy()
