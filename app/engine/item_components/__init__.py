from app.utilities.import_utils import import_submodules


for module in import_submodules(__name__, __path__):
    print("Imported Item Components in %s..." % module.__name__)
