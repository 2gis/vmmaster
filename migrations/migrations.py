# # inside of a "create the database" script, first create
# # tables:
# my_metadata.create_all(engine)

# then, load the Alembic configuration and generate the
# version table, "stamping" it with the most recent rev:
import alembic.util
from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory
from core.utils.init import home_dir

alembic_cfg = Config("%s/migrations/alembic.ini" % home_dir())
script = ScriptDirectory.from_config(alembic_cfg)


def run(connection_string):
    revision = "4f80a6b3ffc2"  # Added selenium log field

    alembic_cfg.set_main_option("sqlalchemy.url", connection_string)
    try:
        command.upgrade(alembic_cfg, revision)
    except alembic.util.CommandError:
        try:
            command.downgrade(alembic_cfg, revision)
        except alembic.util.CommandError:
            raise Exception("Could not upgrade nor downgrade "
                            "database to revision %s" % revision)
