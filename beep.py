"""Short notification beep for the lay-finished signal.

Played through a system player (PipeWire, PulseAudio or ALSA) on a small
generated WAV file, so it does not block the UI; the Qt beep is the last
resort.
"""

import os
import shutil
import struct
import subprocess
import tempfile

BEEP_FREQUENCY = 1200
BEEP_MS = 120

# Players tried in order on Linux (PipeWire, PulseAudio, ALSA).
LINUX_PLAYERS = ("pw-play", "paplay", "aplay")


def beep_wav(frequency=BEEP_FREQUENCY, duration_ms=BEEP_MS, rate=22050):
    """A mono 16-bit WAV of a sine tone with short fades (no clicks)."""
    import math

    count = rate * duration_ms // 1000
    fade = max(1, rate * 5 // 1000)

    samples = bytearray()

    for i in range(count):
        envelope = min(1.0, i / fade, (count - 1 - i) / fade)
        value = 0.5 * envelope * math.sin(2 * math.pi * frequency * i / rate)
        samples += struct.pack("<h", int(value * 32767))

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + len(samples), b"WAVE",
        b"fmt ", 16, 1, 1, rate, rate * 2, 2, 16,
        b"data", len(samples)
    )

    return header + bytes(samples)


_beep_file = None


def linux_beep_command():
    """Command that plays the beep on Linux, None without a player."""
    global _beep_file

    player = next(
        (path for path in map(shutil.which, LINUX_PLAYERS) if path), None
    )

    if player is None:
        return None

    if _beep_file is None or not os.path.exists(_beep_file):
        handle, path = tempfile.mkstemp(prefix="squad-ballistics-", suffix=".wav")

        with os.fdopen(handle, "wb") as f:
            f.write(beep_wav())

        _beep_file = path

    return [player, _beep_file]


def beep():
    """Short high beep that does not block the UI."""
    command = linux_beep_command()

    if command is not None:
        try:
            subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            return
        except OSError:
            pass

    # Often muted on desktops: only the last resort.
    from PyQt6.QtWidgets import QApplication

    QApplication.beep()
