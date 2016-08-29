import muffin
from worker.app import create_app


app = application = create_app()
muffin.import_submodules(__name__)
