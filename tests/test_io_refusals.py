"""The data readers refuse each kind of malformed file with a DataError naming the reason (one case per branch the
coverage run found unexercised), and read a .npy file of format 2.0, written here byte by byte from the NumPy format
specification (magic, version, 4-byte header length, a Python-literal header padded to a multiple of 64)."""
import json
import os
import shutil
import struct
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from exactfig.data import io  # noqa: E402


def npy_v2(rows):
    h, w = len(rows), len(rows[0])
    header = f"{{'descr': '<f8', 'fortran_order': False, 'shape': ({h}, {w}), }}"
    pad = 64 - (12 + len(header) + 1) % 64
    header = header + " " * pad + "\n"
    body = b"".join(struct.pack("<d", v) for row in rows for v in row)
    return b"\x93NUMPY" + bytes((2, 0)) + struct.pack("<I", len(header)) + header.encode("latin-1") + body


class TestIoRefusals(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="exactfig-io-")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def path(self, name, data):
        p = os.path.join(self.d, name)
        with open(p, "wb") as fh:
            fh.write(data if isinstance(data, bytes) else data.encode("utf-8"))
        return p

    def refuses(self, reader, name, data, why):
        with self.assertRaisesRegex(io.DataError, why, msg=name):
            reader(self.path(name, data))

    def test_netpbm(self):
        self.refuses(io.read_pgm, "a.pgm", "P7\n2 2\n255\n", "not a PGM")
        self.refuses(io.read_pgm, "b.pgm", "P2\n2\n", "bad PGM header")
        self.refuses(io.read_pgm, "c.pgm", "P2\n0 2\n255\n", "bad PGM size or maxval")
        self.refuses(io.read_ppm, "a.ppm", "P5\n1 1\n255\n\x00", "not a PPM")
        self.refuses(io.read_ppm, "b.ppm", "P3\n1\n", "bad PPM header")
        self.refuses(io.read_ppm, "c.ppm", "P3\n1 1\n65535\n1 2 3\n", "only 8-bit PPM")

    def test_npy(self):
        self.refuses(io.read_npy, "a.npy", b"not numpy at all", "not a .npy")
        g = io.read_npy(self.path("v2.npy", npy_v2([[1.0, 2.0], [3.0, -0.5]])))
        self.assertEqual(g.values, [[1.0, 2.0], [3.0, -0.5]])

    def test_json_shapes(self):
        self.refuses(io.read_grid_json, "a.json", "{not json", "not valid JSON")
        self.refuses(io.read_points_json, "b.json", json.dumps({"points": [[1, 2]]}), "list of \\[x")
        self.refuses(io.read_points_json, "c.json", json.dumps({"x": [1, 2], "y": [1], "value": [1, 2]}),
                     "different length")
        self.refuses(io.read_frames_json, "d.json", json.dumps({"frame": []}), "expected")
        self.refuses(io.read_frames_json, "e.json", json.dumps({"frames": [[[0]]] * 1001}), "frames is more")
        self.refuses(io.read_frames_json, "f.json", json.dumps({"frames": [5]}), "is not a list of rows")

    def test_text_encodings(self):
        self.refuses(io.read_grid_csv, "a.csv", b"\xff\xfe" + b"1\x00,\x00" + b"\x00\xd8", "UTF-16")


if __name__ == "__main__":
    unittest.main()
