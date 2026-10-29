"""QR encoder: reference values from ISO/IEC 18004 and an independent decoder.

The decoder is ZXing-C++ (`pip install zxing-cpp`, see requirements-dev.txt
and the CI workflow): a symbol only counts as right when a reader that
shares no code with `qr.py` gets the text, version, level and mask back.
"""

import pytest

import qr

# Byte-mode capacity at level M, versions 1-10 (ISO/IEC 18004 table 7).
CAPACITY_M = (14, 26, 42, 62, 84, 106, 122, 152, 180, 213)

# Format bits of level M with masks 0-7 (ISO/IEC 18004 table C.1).
FORMAT_BITS_M = (
    0b101010000010010,
    0b101000100100101,
    0b101111001111100,
    0b101101101001011,
    0b100010111111001,
    0b100000011001110,
    0b100111110010111,
    0b100101010100000,
)

# Version information bits (ISO/IEC 18004 table D.1).
VERSION_BITS = {7: 0x07C94, 8: 0x085BC, 9: 0x09A99, 10: 0x0A4D3}

DEVICE_LINK = "https://calc.tk104.duckdns.org/#link=ABCDEFGHJKLM"


def decode(matrix, module=1):
    """Text, version, level and mask that ZXing-C++ reads off `matrix`."""
    zxingcpp = pytest.importorskip("zxingcpp")

    quiet = 4
    side = (len(matrix) + 2 * quiet) * module
    pixels = bytearray(b"\xff" * side * side)

    for row, modules in enumerate(matrix):
        for column, dark in enumerate(modules):
            if not dark:
                continue

            for y in range((row + quiet) * module, (row + quiet + 1) * module):
                start = y * side + (column + quiet) * module
                pixels[start:start + module] = b"\x00" * module

    image = zxingcpp.ImageView(pixels, side, side, zxingcpp.ImageFormat.Lum)
    results = zxingcpp.read_barcodes(image, formats=zxingcpp.BarcodeFormat.QRCode)

    assert len(results) == 1, "the decoder found no QR code"

    extra = results[0].extra

    return results[0].text, int(extra["Version"]), extra["ECLevel"], extra["DataMask"]


@pytest.mark.parametrize("version", range(1, qr.MAX_VERSION + 1))
def test_every_version_decodes_at_its_capacity(version):
    """The longest text of each version: all block layouts and alignment grids."""
    text = "".join(chr(ord("a") + i % 26) for i in range(CAPACITY_M[version - 1]))

    matrix = qr.qr_matrix(text)

    assert len(matrix) == qr.size_of(version)
    assert decode(matrix)[:3] == (text, version, "M")


@pytest.mark.parametrize("mask", range(8))
def test_every_mask_decodes(mask):
    for text in (DEVICE_LINK, "x" * CAPACITY_M[6]):
        assert decode(qr.qr_matrix(text, mask=mask)) == (
            text, qr.choose_version(len(text)), "M", mask
        )


def test_device_link_decodes_at_the_size_the_app_shows():
    text, version, level, _mask = decode(qr.qr_matrix(DEVICE_LINK), module=4)

    assert (text, version, level) == (DEVICE_LINK, 4, "M")


def test_utf8_text_decodes():
    text = "Связь 🎯 SquadCalc"

    assert decode(qr.qr_matrix(text))[0] == text


@pytest.mark.parametrize("version", range(1, qr.MAX_VERSION + 1))
def test_version_choice_matches_the_capacity_table(version):
    capacity = CAPACITY_M[version - 1]

    assert qr.data_capacity(version) * 8 >= 4 + qr.count_bits(version) + 8 * capacity
    assert qr.choose_version(capacity) == version

    if version < qr.MAX_VERSION:
        assert qr.choose_version(capacity + 1) == version + 1


def test_too_long_text_is_refused():
    assert qr.choose_version(CAPACITY_M[-1] + 1) is None

    with pytest.raises(ValueError):
        qr.qr_matrix("x" * (CAPACITY_M[-1] + 1))


def test_format_and_version_bits_match_the_standard():
    assert tuple(qr._bch_format(mask) for mask in range(8)) == FORMAT_BITS_M

    for version, bits in VERSION_BITS.items():
        assert qr._bch_version(version) == bits


def test_reed_solomon_matches_the_standard_example():
    """Version 1-M "01234567" (ISO/IEC 18004 annex I): its 10 EC codewords."""
    data = [16, 32, 12, 86, 97, 128, 236, 17, 236, 17, 236, 17, 236, 17, 236, 17]

    assert qr._rs_remainder(data, qr._rs_divisor(10)) == [
        165, 36, 212, 193, 237, 54, 199, 135, 44, 85
    ]


def test_alignment_positions_match_the_standard():
    """Annex E for the versions with one and with several alignment rows."""
    assert qr.alignment_positions(1) == []
    assert qr.alignment_positions(2) == [6, 18]
    assert qr.alignment_positions(6) == [6, 34]
    assert qr.alignment_positions(7) == [6, 22, 38]
    assert qr.alignment_positions(10) == [6, 28, 50]


def test_best_mask_has_the_lowest_penalty():
    best = qr.qr_matrix(DEVICE_LINK)

    assert qr.penalty(best) == min(
        qr.penalty(qr.qr_matrix(DEVICE_LINK, mask=mask)) for mask in range(8)
    )
