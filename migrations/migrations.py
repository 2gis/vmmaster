# # inside of a "create the database" script, first create
# # tables:
# my_metadata.create_all(engine)

# then, load the Alembic configuration and generate the
# version table, "stamping" it with the most recent rev:
from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory
from core.utils.init import home_dir

alembic_cfg = Config("%s/migrations/alembic.ini" % home_dir())
script = ScriptDirectory.from_config(alembic_cfg)


def run(connection_string):
    revision = "2919ba26959e"

    alembic_cfg.set_main_option("sqlalchemy.url", connection_string)
    command.upgrade(alembic_cfg, revision)
