# coding: utf-8

import logging
from flask import Flask

from twisted.internet import reactor
from flask.ext.script import Manager

from core.config import setup_config, config
from core.utils.init import home_dir, useradd
from core.logger import setup_logging
from core.utils import change_user_vmmaster

setup_config('%s/config.py' % home_dir())
setup_logging(
    log_type=getattr(config, "LOG_TYPE", None),
    log_level=getattr(config, "LOG_LEVEL", None)
)
app = Flask(__name__)
manager = Manager(app)
log = logging.getLogger(__name__)


@manager.command
def runserver():
    """
    Run server
    """
    from vmmaster.server import VMMasterServer
    VMMasterServer(reactor, config.PORT).run()


@manager.command
def runprovider():
    """
    Run provider
    """
    from vmpool.server import ProviderServer
    ProviderServer(reactor, config.PORT).run()


@manager.command
def cleanup():
    """
    Run cleanup
    """
    from vmmaster import cleanup
    cleanup.run()


@manager.command
def init():
    """
    Initialize application
    """
    log.info('Initialize application')
    useradd()
    change_user_vmmaster()
    exit(0)


@manager.command
def migrations():
    """
    Database migrations
    """
    from migrations import migrations
    migrations.run(config.DATABASE)


@manager.command
def version():
    """
    Show application version
    """
    import versioneer

    versioneer.VCS = 'git'
    versioneer.versionfile_source = 'vmmaster/_version.py'
    versioneer.versionfile_build = 'vmmaster/_version.py'
    versioneer.tag_prefix = ''  # tags are like 0.1.0
    versioneer.parentdir_prefix = 'vmmaster-'  # dirname like 'myproject-0.1.0'

    return versioneer.get_version()


if __name__ == '__main__':
    manager.run()
