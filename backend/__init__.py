import muffin
from backend.app import create_app


app = application = create_app()

import backend.webdriver.views
muffin.import_submodules(__name__)
