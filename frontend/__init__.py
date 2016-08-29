import muffin
from frontend.app import create_app


app = application = create_app()

import frontend.views
muffin.import_submodules(__name__)
