"""Small helpers shared by the app's modules."""

import os

# How far the width / height of a screen may be from 16:9 and still count as
# 16:9: 1366x768 (1.7786) rounds to 16:9 (1.7778); 16:10 (1.6) does not.
ASPECT_TOLERANCE = 0.02


def is_16_9(width, height):
    """Whether a `width` x `height` screen is 16:9 within `ASPECT_TOLERANCE`.

    The sight and compass readers are made for 16:9 screens (1920x1080 and
    2560x1440 are the tested sizes; other 16:9 sizes scale with the height).
    A zero or negative size is not 16:9.
    """
    if width <= 0 or height <= 0:
        return False

    return abs(width / height - 16 / 9) <= ASPECT_TOLERANCE


def resource_path(relative_path):
    """Absolute path to a data file of the app (weapons.json, assets)."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)
