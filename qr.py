"""QR codes for short texts (the device link), without a dependency.

`qr_matrix(text)` encodes UTF-8 text in byte mode with error correction
level M (15 % of the symbol may be damaged) into the smallest of versions
1-10 (up to 213 bytes, 57x57 modules) and returns the modules, True =
dark, without the quiet zone (leave 4 light modules around it).

Follows ISO/IEC 18004:2015: Reed-Solomon over GF(256) with the polynomial
0x11D, the block layout of table 9, the zigzag placement of 7.7.3 and the
mask chosen by the penalty rules of 7.8.3. The tests decode the result with
an independent decoder (ZXing-C++).
"""

# Byte-mode indicator (ISO/IEC 18004 table 2).
BYTE_MODE = 0b0100

# Format bits of error correction level M (table 12).
ECC_M_BITS = 0b00

MAX_VERSION = 10

# Level M, per version: (error correction codewords per block, blocks)
# (table 9). Blocks are as long as the codewords allow; the last ones are
# one data codeword longer when they do not divide evenly.
ECC_M_BLOCKS = {
    1: (10, 1),
    2: (16, 1),
    3: (26, 1),
    4: (18, 2),
    5: (24, 2),
    6: (16, 4),
    7: (18, 4),
    8: (22, 4),
    9: (22, 5),
    10: (26, 5),
}

PAD_BYTES = (0xEC, 0x11)

# Penalty weights N1-N4 of the mask evaluation (7.8.3.1).
PENALTY_RUN, PENALTY_BLOCK, PENALTY_FINDER, PENALTY_BALANCE = 3, 3, 40, 10

MASKS = (
    lambda r, c: (r + c) % 2 == 0,
    lambda r, c: r % 2 == 0,
    lambda r, c: c % 3 == 0,
    lambda r, c: (r + c) % 3 == 0,
    lambda r, c: (r // 2 + c // 3) % 2 == 0,
    lambda r, c: r * c % 2 + r * c % 3 == 0,
    lambda r, c: (r * c % 2 + r * c % 3) % 2 == 0,
    lambda r, c: ((r + c) % 2 + r * c % 3) % 2 == 0,
)


def size_of(version):
    """Modules per side of a symbol of `version`."""
    return 17 + 4 * version


def alignment_positions(version):
    """Row/column centres of the alignment patterns (annex E)."""
    if version == 1:
        return []

    count = version // 7 + 2
    step = (version * 8 + count * 3 + 5) // (count * 4 - 4) * 2
    last = size_of(version) - 7

    return [6] + [last - step * i for i in reversed(range(count - 1))]


def total_codewords(version):
    """Data plus error correction codewords that fit in `version`."""
    modules = (16 * version + 128) * version + 64

    if version >= 2:
        count = version // 7 + 2
        modules -= (25 * count - 10) * count - 55

    if version >= 7:
        modules -= 36

    return modules // 8


def data_capacity(version):
    """Data codewords of `version` at level M."""
    ecc, blocks = ECC_M_BLOCKS[version]

    return total_codewords(version) - ecc * blocks


def count_bits(version):
    """Width of the byte-mode character count (table 3)."""
    return 8 if version <= 9 else 16


def _gf_multiply(x, y):
    """Product in GF(256) modulo x^8 + x^4 + x^3 + x^2 + 1 (0x11D)."""
    product = 0

    for bit in range(7, -1, -1):
        product = (product << 1) ^ (0x11D if product & 0x80 else 0)

        if y >> bit & 1:
            product ^= x

    return product


def _rs_divisor(degree):
    """Generator polynomial (x - a^0)...(x - a^(degree-1)), leading 1 dropped."""
    divisor = [0] * (degree - 1) + [1]
    root = 1

    for _ in range(degree):
        for i in range(degree):
            divisor[i] = _gf_multiply(divisor[i], root)

            if i + 1 < degree:
                divisor[i] ^= divisor[i + 1]

        root = _gf_multiply(root, 0x02)

    return divisor


def _rs_remainder(data, divisor):
    """Error correction codewords of `data` (polynomial division remainder)."""
    remainder = [0] * len(divisor)

    for byte in data:
        factor = byte ^ remainder.pop(0)
        remainder.append(0)

        for i, coefficient in enumerate(divisor):
            remainder[i] ^= _gf_multiply(coefficient, factor)

    return remainder


def _bch_format(mask):
    """15 format bits: level M, `mask`, BCH(15,5) and the XOR mask (7.9)."""
    data = ECC_M_BITS << 3 | mask
    remainder = data

    for _ in range(10):
        remainder = (remainder << 1) ^ ((remainder >> 9) * 0x537)

    return (data << 10 | remainder) ^ 0x5412


def _bch_version(version):
    """18 version bits: `version` and its BCH(18,6) code (7.10)."""
    remainder = version

    for _ in range(12):
        remainder = (remainder << 1) ^ ((remainder >> 11) * 0x1F25)

    return version << 12 | remainder


def choose_version(length):
    """Smallest version holding `length` bytes at level M, None if none."""
    for version in range(1, MAX_VERSION + 1):
        needed_bits = 4 + count_bits(version) + 8 * length

        if needed_bits <= data_capacity(version) * 8:
            return version

    return None


def data_codewords(payload, version):
    """Mode, count, payload, terminator and padding as codewords (7.4)."""
    capacity = data_capacity(version) * 8

    bits = []

    def append(value, width):
        bits.extend(value >> i & 1 for i in reversed(range(width)))

    append(BYTE_MODE, 4)
    append(len(payload), count_bits(version))

    for byte in payload:
        append(byte, 8)

    append(0, min(4, capacity - len(bits)))
    append(0, -len(bits) % 8)

    codewords = [
        int("".join(map(str, bits[i:i + 8])), 2)
        for i in range(0, len(bits), 8)
    ]

    for i in range(data_capacity(version) - len(codewords)):
        codewords.append(PAD_BYTES[i % 2])

    return codewords


def interleave(codewords, version):
    """Data split into blocks, each with its error correction, interleaved (7.6)."""
    ecc, count = ECC_M_BLOCKS[version]
    short_length = data_capacity(version) // count
    long_blocks = data_capacity(version) % count
    divisor = _rs_divisor(ecc)

    blocks, start = [], 0

    for index in range(count):
        length = short_length + (index >= count - long_blocks)
        blocks.append(codewords[start:start + length])
        start += length

    corrections = [_rs_remainder(block, divisor) for block in blocks]

    result = []

    for i in range(short_length + 1):
        result.extend(block[i] for block in blocks if i < len(block))

    for i in range(ecc):
        result.extend(correction[i] for correction in corrections)

    return result


class _Symbol:
    """Modules of one symbol and which of them are function patterns."""

    def __init__(self, version):
        self.version = version
        self.size = size_of(version)
        self.dark = [[False] * self.size for _ in range(self.size)]
        self.reserved = [[False] * self.size for _ in range(self.size)]

        self.draw_function_patterns()

    def set(self, row, column, dark):
        self.dark[row][column] = dark
        self.reserved[row][column] = True

    def draw_function_patterns(self):
        size = self.size

        for i in range(size):
            self.set(6, i, i % 2 == 0)
            self.set(i, 6, i % 2 == 0)

        for row, column in ((3, 3), (3, size - 4), (size - 4, 3)):
            self.draw_finder(row, column)

        positions = alignment_positions(self.version)
        corners = {(6, 6), (6, size - 7), (size - 7, 6)}

        for row in positions:
            for column in positions:
                if (row, column) not in corners:
                    self.draw_alignment(row, column)

        # Placeholders: the real format bits come with the mask.
        self.draw_format(0)

        if self.version >= 7:
            self.draw_version()

    def draw_finder(self, row, column):
        """7x7 finder centred at (row, column) and its light separator."""
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                r, c = row + dy, column + dx

                if 0 <= r < self.size and 0 <= c < self.size:
                    distance = max(abs(dy), abs(dx))
                    self.set(r, c, distance not in (2, 4))

    def draw_alignment(self, row, column):
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                self.set(row + dy, column + dx, max(abs(dy), abs(dx)) != 1)

    def draw_format(self, mask):
        bits = _bch_format(mask)
        size = self.size

        def bit(i):
            return bool(bits >> i & 1)

        # Around the top-left finder.
        for i in range(6):
            self.set(i, 8, bit(i))

        self.set(7, 8, bit(6))
        self.set(8, 8, bit(7))
        self.set(8, 7, bit(8))

        for i in range(9, 15):
            self.set(8, 14 - i, bit(i))

        # Split between the other two finders.
        for i in range(8):
            self.set(8, size - 1 - i, bit(i))

        for i in range(8, 15):
            self.set(size - 15 + i, 8, bit(i))

        self.set(size - 8, 8, True)

    def draw_version(self):
        bits = _bch_version(self.version)

        for i in range(18):
            dark = bool(bits >> i & 1)
            a, b = self.size - 11 + i % 3, i // 3

            self.set(b, a, dark)
            self.set(a, b, dark)

    def draw_codewords(self, codewords):
        """Codeword bits in the two-column zigzag from the bottom right (7.7.3)."""
        bits = [byte >> (7 - i) & 1 for byte in codewords for i in range(8)]
        index = 0
        column = self.size - 1

        while column >= 1:
            if column == 6:
                column = 5

            for step in range(self.size):
                upward = (column + 1) & 2 == 0
                row = self.size - 1 - step if upward else step

                for c in (column, column - 1):
                    if self.reserved[row][c]:
                        continue

                    # Remainder bits past the codewords stay light.
                    if index < len(bits):
                        self.dark[row][c] = bool(bits[index])

                    index += 1

            column -= 2

    def apply_mask(self, mask):
        """XOR mask `mask` over the data modules (applying it twice undoes it)."""
        condition = MASKS[mask]

        for row in range(self.size):
            for column in range(self.size):
                if not self.reserved[row][column] and condition(row, column):
                    self.dark[row][column] = not self.dark[row][column]


def _run_penalty(line):
    """Rule 1 for one row or column: runs of 5+ same-colour modules."""
    penalty, run, previous = 0, 0, None

    for module in line:
        if module == previous:
            run += 1
        else:
            if run >= 5:
                penalty += PENALTY_RUN + run - 5

            previous, run = module, 1

    if run >= 5:
        penalty += PENALTY_RUN + run - 5

    return penalty


# Rule 3: 1:1:3:1:1 finder-like pattern with four light modules on a side.
_FINDER_LIKE = (
    (True, False, True, True, True, False, True, False, False, False, False),
    (False, False, False, False, True, False, True, True, True, False, True),
)


def _finder_penalty(line):
    """Rule 3 for one row or column; outside the symbol counts as light."""
    padded = (False,) * 4 + tuple(line) + (False,) * 4
    count = 0

    for start in range(len(padded) - 10):
        if padded[start:start + 11] in _FINDER_LIKE:
            count += 1

    return count * PENALTY_FINDER


def penalty(dark):
    """Penalty score of a masked symbol (7.8.3.1); lower is better."""
    size = len(dark)
    columns = [[dark[r][c] for r in range(size)] for c in range(size)]
    score = 0

    for line in list(dark) + columns:
        score += _run_penalty(line) + _finder_penalty(line)

    for r in range(size - 1):
        for c in range(size - 1):
            if dark[r][c] == dark[r][c + 1] == dark[r + 1][c] == dark[r + 1][c + 1]:
                score += PENALTY_BLOCK

    # Every whole 5 % the dark share is away from 50 % costs N4.
    dark_share = sum(map(sum, dark)) * 100 // (size * size)

    return score + abs(dark_share - 50) // 5 * PENALTY_BALANCE


def qr_matrix(text, mask=None):
    """Modules (rows of booleans, True = dark) of the QR code of `text`.

    The quiet zone is not included. `mask` (0-7) forces a mask pattern;
    None picks the one with the lowest penalty, as the standard asks.
    Raises ValueError if the text is longer than version 10 at level M
    holds (213 bytes of UTF-8).
    """
    payload = str(text).encode("utf-8")
    version = choose_version(len(payload))

    if version is None:
        raise ValueError(f"{len(payload)} bytes do not fit in a version {MAX_VERSION} QR code")

    codewords = interleave(data_codewords(payload, version), version)

    best = None

    for candidate in range(len(MASKS)) if mask is None else (mask,):
        symbol = _Symbol(version)
        symbol.draw_codewords(codewords)
        symbol.apply_mask(candidate)
        symbol.draw_format(candidate)

        score = penalty(symbol.dark)

        if best is None or score < best[0]:
            best = (score, symbol)

    return best[1].dark
