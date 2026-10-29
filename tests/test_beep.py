import os

import beep


def test_beep_wav_is_a_valid_tone():
    import io
    import wave

    with wave.open(io.BytesIO(beep.beep_wav())) as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        frames = w.readframes(w.getnframes())
        assert w.getnframes() == w.getframerate() * beep.BEEP_MS // 1000

    samples = [int.from_bytes(frames[i:i + 2], "little", signed=True)
               for i in range(0, len(frames), 2)]
    assert max(samples) > 10000
    assert samples[0] == 0  # faded in: no click


def test_linux_beep_uses_the_first_player_found(monkeypatch, tmp_path):
    players = {"paplay": "/usr/bin/paplay", "aplay": "/usr/bin/aplay"}
    monkeypatch.setattr(beep.shutil, "which", players.get)
    monkeypatch.setattr(beep, "_beep_file", None)
    monkeypatch.setattr(beep.tempfile, "tempdir", str(tmp_path))

    command = beep.linux_beep_command()

    assert command[0] == "/usr/bin/paplay"
    assert os.path.getsize(command[1]) > 44

    monkeypatch.setattr(beep.shutil, "which", lambda name: None)
    assert beep.linux_beep_command() is None
