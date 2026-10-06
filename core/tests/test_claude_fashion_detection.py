import io
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from PIL import Image

from core.listings.claude_fashion_detection import ClaudeFashionDetector


def make_detector(response_text=None, stop_reason='end_turn', content=None):
    with patch('core.listings.claude_fashion_detection.anthropic.Anthropic'):
        detector = ClaudeFashionDetector()
    blocks = content if content is not None else [
        SimpleNamespace(type='thinking', thinking=''),
        SimpleNamespace(type='text', text=response_text),
    ]
    detector.client = MagicMock()
    detector.client.messages.create.return_value = SimpleNamespace(content=blocks, stop_reason=stop_reason)
    return detector


def png_bytes(mode='RGBA', size=(40, 40)):
    buffer = io.BytesIO()
    Image.new(mode, size).save(buffer, format='PNG')
    buffer.seek(0)
    return buffer


class ClaudeFashionDetectorTests(SimpleTestCase):
    def test_parses_json_after_thinking_block(self):
        detector = make_detector('{"items": [{"category": "dress"}], "primary_category": "dress", '
                                 '"overall_colors": ["Red"], "confidence": 0.9}')
        result = detector.detect_fashion_objects(png_bytes())

        self.assertEqual(result['primary_category'], 'dress')
        self.assertEqual(result['total_objects'], 1)
        self.assertEqual(result['detected_colors'], ['Red'])

    def test_strips_markdown_code_fence(self):
        detector = make_detector('```json\n{"items": [], "primary_category": "bag"}\n```')
        self.assertEqual(detector.detect_fashion_objects(png_bytes())['primary_category'], 'bag')

    def test_invalid_json_falls_back_to_generic_clothing(self):
        detector = make_detector('not json')
        self.assertEqual(detector.detect_fashion_objects(png_bytes())['primary_category'], 'clothing')

    def test_refusal_is_reported_as_error(self):
        detector = make_detector(content=[], stop_reason='refusal')
        result = detector.detect_fashion_objects(png_bytes())
        self.assertIn('declined', result['error'])
        self.assertEqual(result['detected_objects'], [])

    def test_images_are_converted_to_jpeg_and_downsized(self):
        detector = make_detector('{}')
        data, media_type = detector._prepare_image(png_bytes(size=(3000, 1000)))

        self.assertEqual(media_type, 'image/jpeg')
        import base64
        image = Image.open(io.BytesIO(base64.b64decode(data)))
        self.assertEqual(image.mode, 'RGB')
        self.assertEqual(max(image.size), 1568)
