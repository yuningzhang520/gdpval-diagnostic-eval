"""I2 regressions for harness.tools.validate_image_bytes (host side, no Docker, no model):
valid images pass with the actual format's MIME, corrupt or truncated data is refused,
extension/format mismatches are refused, byte and pixel limits are enforced.
Run: python -m unittest harness.tests.test_image_unit -v"""
import unittest
from io import BytesIO

from PIL import Image
from inspect_ai.tool import ToolError

from harness import tools as T


def png(w=16, h=8, mode="RGB", **save):
    buf = BytesIO(); Image.new(mode, (w, h), (200, 30, 30) if mode == "RGB" else 1).save(buf, format="PNG", **save); return buf.getvalue()


def jpeg(w=16, h=8):
    buf = BytesIO(); Image.new("RGB", (w, h), (10, 200, 10)).save(buf, format="JPEG"); return buf.getvalue()


class ImageValidationTests(unittest.TestCase):
    def test_valid_png_jpeg_gif_webp(self):
        info = T.validate_image_bytes(png(), ".png")
        self.assertEqual((info["format"], info["mime"], info["width"], info["height"]), ("PNG", "image/png", 16, 8))
        self.assertEqual(T.validate_image_bytes(jpeg(), ".jpg")["mime"], "image/jpeg")
        self.assertEqual(T.validate_image_bytes(jpeg(), ".jpeg")["format"], "JPEG")
        buf = BytesIO(); Image.new("P", (4, 4)).save(buf, format="GIF"); self.assertEqual(T.validate_image_bytes(buf.getvalue(), ".gif")["format"], "GIF")
        buf = BytesIO(); Image.new("RGB", (4, 4)).save(buf, format="WEBP"); self.assertEqual(T.validate_image_bytes(buf.getvalue(), ".webp")["format"], "WEBP")

    def test_corrupt_and_truncated_refused(self):
        # Random bytes are refused either as undecodable or, when Pillow's header sniffing reads an
        # absurd size out of them, by the pixel guard; both are refusals before any decode.
        with self.assertRaisesRegex(ToolError, "could not be decoded|pixels"):
            T.validate_image_bytes(b"\x00\x01\x02 not an image at all", ".png")
        with self.assertRaisesRegex(ToolError, "could not be decoded|pixels|does not match"):
            T.validate_image_bytes(bytes(range(256)) * 16, ".png")
        data = png(64, 64)
        with self.assertRaisesRegex(ToolError, "could not be decoded"):
            T.validate_image_bytes(data[: len(data) // 2], ".png")  # truncated after the header
        with self.assertRaisesRegex(ToolError, "empty"):
            T.validate_image_bytes(b"", ".png")

    def test_extension_format_mismatch_refused(self):
        with self.assertRaisesRegex(ToolError, "does not match"):
            T.validate_image_bytes(jpeg(), ".png")
        with self.assertRaisesRegex(ToolError, "does not match"):
            T.validate_image_bytes(png(), ".jpg")
        buf = BytesIO(); Image.new("RGB", (4, 4)).save(buf, format="BMP")
        with self.assertRaisesRegex(ToolError, "does not match|unsupported"):
            T.validate_image_bytes(buf.getvalue(), ".png")
        with self.assertRaisesRegex(ToolError, "unsupported image type"):
            T.validate_image_bytes(png(), ".bmp")

    def test_pixel_limits_refused_before_decoding(self):
        big = png(9000, 9000, mode="1")  # 81 MP but only a few kB of PNG data
        self.assertLess(len(big), 100_000)
        with self.assertRaisesRegex(ToolError, "pixels"):  # refused by the pixel guard (Pillow bomb guard or our explicit check), never decoded
            T.validate_image_bytes(big, ".png")
        wide = png(8001, 1, mode="1")
        with self.assertRaisesRegex(ToolError, "pixels; limits"):
            T.validate_image_bytes(wide, ".png")
        mid = png(5000, 5000, mode="1")  # 25 MP: above our total but below Pillow's 2x guard -> our explicit check
        with self.assertRaisesRegex(ToolError, "pixels; limits"):
            T.validate_image_bytes(mid, ".png")
        ok = png(4000, 4000, mode="1")  # 16 MP, within limits
        self.assertEqual(T.validate_image_bytes(ok, ".png")["width"], 4000)

    def test_byte_limit_refused(self):
        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * T.MAX_IMAGE_BYTES
        with self.assertRaisesRegex(ToolError, "limit is"):
            T.validate_image_bytes(data, ".png")


if __name__ == "__main__":
    unittest.main()
