from django.test import SimpleTestCase
from PIL import Image

from core.image_utils import resize_image


class ResizeImageTests(SimpleTestCase):
    def test_scales_smallest_side_to_target_and_keeps_aspect_ratio(self):
        resized = resize_image(Image.new('RGB', (1200, 800)), size=(400, 400))
        self.assertEqual(resized.size, (600, 400))

    def test_upscales_small_images(self):
        resized = resize_image(Image.new('RGB', (100, 200)), size=(400, 400))
        self.assertEqual(resized.size, (400, 800))

    def test_preserves_transparency(self):
        resized = resize_image(Image.new('RGBA', (800, 800)), size=(400, 400))
        self.assertEqual(resized.mode, 'RGBA')

    def test_converts_opaque_images_to_rgb(self):
        resized = resize_image(Image.new('L', (800, 800)), size=(400, 400))
        self.assertEqual(resized.mode, 'RGB')
