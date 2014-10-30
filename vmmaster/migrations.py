# # inside of a "create the database" script, first create
# # tables:
# my_metadata.create_all(engine)

# then, load the Alembic configuration and generate the
# version table, "stamping" it with the most recent rev:
from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory
import os

alembic_cfg = Config("%s/alembic.ini" % os.path.dirname(os.path.abspath(__file__)))
script = ScriptDirectory.from_config(alembic_cfg)


def run(connection_string):
    alembic_cfg.set_main_option("sqlalchemy.url", connection_string)
    command.upgrade(alembic_cfg, "1eb29cd1981")