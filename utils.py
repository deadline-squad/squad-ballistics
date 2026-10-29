import os


def resource_path(relative_path):
    """Absolute path to a data file of the app (weapons.json, assets)."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)
