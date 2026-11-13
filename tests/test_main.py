import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import convert_image, fit_image, load_config


class ImageConversionTests(unittest.TestCase):
    def test_config_rejects_unauthorized_target_size(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            config_path = Path(temporary_directory) / "config.json"
            config_path.write_text(
                '{"target_sizes": [{"width": 1920, "height": 886}]}',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "Format App Store non autorisé"):
                load_config(config_path)

    def test_exact_dimensions_and_png_output(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "capture été.jpg"
            destination = root / "output" / "1320x2868" / "capture été.png"
            Image.new("RGB", (300, 500), "#325577").save(source)
            config = {
                "inner_margin": 0,
                "fallback_color": "#20212A",
                "extension_mode": "gradient",
                "sharpening": 0,
            }

            original_size, final_size = convert_image(source, destination, (1320, 2868), config)

            self.assertEqual(original_size, (300, 500))
            self.assertEqual(final_size, (1320, 2868))
            with Image.open(destination) as result:
                self.assertEqual(result.format, "PNG")
                self.assertEqual(result.size, (1320, 2868))

    def test_contain_preserves_aspect_ratio_and_all_corners(self):
        source = Image.new("RGB", (40, 80), "white")
        source.paste("red", (0, 0, 8, 8))
        source.paste("green", (32, 0, 40, 8))
        source.paste("blue", (0, 72, 8, 80))
        source.paste("yellow", (32, 72, 40, 80))

        canvas, resized_size, offset = fit_image(source, (60, 100))

        self.assertEqual(resized_size, (50, 100))
        self.assertEqual(offset, (5, 0))
        self.assertEqual(resized_size[0] / resized_size[1], 40 / 80)
        self.assertEqual(canvas.getpixel((6, 1)), (255, 0, 0))
        self.assertEqual(canvas.getpixel((53, 1)), (0, 128, 0))
        self.assertEqual(canvas.getpixel((6, 98)), (0, 0, 255))
        self.assertEqual(canvas.getpixel((53, 98)), (255, 255, 0))

    def test_margin_reduces_content_area_without_cropping(self):
        source = Image.new("RGB", (30, 60), "purple")
        _, resized_size, offset = fit_image(source, (100, 200), margin=10)

        self.assertEqual(resized_size, (80, 160))
        self.assertEqual(offset, (10, 20))

    def test_fully_transparent_source_keeps_transparent_output(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "transparent.png"
            destination = root / "transparent-output.png"
            Image.new("RGBA", (8, 8), (0, 0, 0, 0)).save(source)
            config = {
                "inner_margin": 0,
                "fallback_color": "#20212A",
                "extension_mode": "gradient",
                "sharpening": 0,
            }

            convert_image(source, destination, (8, 8), config)

            with Image.open(destination) as result:
                self.assertEqual(result.mode, "RGBA")
                self.assertEqual(result.getpixel((4, 4))[3], 0)


if __name__ == "__main__":
    unittest.main()
