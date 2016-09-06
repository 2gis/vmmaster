import muffin
from backend.app import create_app


app = application = create_app()
import backend.webdriver.views
import backend.api.views
muffin.import_submodules(__name__)
