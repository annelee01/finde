# claude_fashion_detection.py
import json
import base64
import logging
from typing import Dict
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import anthropic
from PIL import Image
import io

logger = logging.getLogger(__name__)

CLAUDE_VISION_MODEL = "claude-opus-5-5"

class ClaudeFashionDetector:
    """
    Simplified fashion detector using Claude Vision API.
    Replaces the complex rule-based system with a single API call.
    """
    
    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=settings.ANTHROPIC_API_KEY
        )
    
    def detect_fashion_objects(self, image_file) -> Dict:
        """
        Main detection method using Claude Vision API.
        
        Args:
            image_file: Django UploadedFile or PIL Image
            
        Returns:
            Dict with detected objects and metadata
        """
        try:
            # Convert image to base64
            image_data, media_type = self._prepare_image(image_file)
            
            # Call Claude Vision API
            response = self._call_claude_vision(image_data, media_type)
            
            # Parse and format response
            results = self._parse_claude_response(response)
            
            return {
                'detected_objects': results.get('items', []),
                'primary_category': results.get('primary_category'),
                'detected_colors': results.get('overall_colors', []),
                'detection_method': 'claude_vision_api',
                'total_objects': len(results.get('items', [])),
                'confidence_score': results.get('confidence', 0.95)
            }
            
        except Exception as e:
            logger.error(f"Claude Vision detection failed: {e}")
            return {
                'error': str(e),
                'detected_objects': [],
                'detection_method': 'claude_vision_api_failed'
            }
    
    def _prepare_image(self, image_file) -> tuple:
        """Convert image to base64 for Claude API and return (data, media_type)."""
        try:
            # Read the original image data
            if hasattr(image_file, 'read'):
                image_file.seek(0)
                original_data = image_file.read()
                image_file.seek(0)  # Reset for PIL
            else:
                # Handle PIL Image - convert to bytes first
                buffer = io.BytesIO()
                image_file.save(buffer, format='JPEG')
                original_data = buffer.getvalue()
            
            # Open with PIL to process
            image = Image.open(io.BytesIO(original_data))
            
            # Convert to RGB if necessary (handles RGBA, P mode, etc.)
            if image.mode in ('RGBA', 'P', 'L'):
                # Create white background for transparency
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                if image.mode == 'RGBA':
                    background.paste(image, mask=image.split()[-1])
                    image = background
                else:
                    image = image.convert('RGB')
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Resize if too large (Claude has size limits)
            if max(image.size) > 1568:
                image.thumbnail((1568, 1568), Image.Resampling.LANCZOS)
            
            # Always save as JPEG with consistent format
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=85, optimize=True)
            final_image_data = buffer.getvalue()
            
            # Encode to base64
            base64_data = base64.b64encode(final_image_data).decode('utf-8')
            
            return base64_data, 'image/jpeg'
            
        except Exception as e:
            raise Exception(f"Image preparation failed: {e}")
    
    def _call_claude_vision(self, image_data: str, media_type: str = 'image/jpeg') -> str:
        """Call Claude Vision API with fashion analysis prompt."""
        
        # NOTE: The real prompt encodes a detailed, hand-tuned fashion taxonomy
        # (fabric/neckline/closure/sleeve analysis rules, category vocabulary, etc).
        # That prompt engineering is proprietary and not included in this public repository.
        # This placeholder asks for a minimal JSON shape compatible with _parse_claude_response.
        prompt = """
Analyze this fashion image and return JSON with this structure:

{
  "items": [
    {"category": "item type", "confidence": 0.5, "colors": ["color"], "color_hexes": ["#hex"], "primary_color": "color"}
  ],
  "primary_category": "main garment category",
  "overall_colors": ["dominant colors in image"],
  "confidence": 0.5
}

Return only valid JSON, no explanation text.
"""

        try:
            message = self.client.messages.create(
                model=CLAUDE_VISION_MODEL,
                max_tokens=16000,
                # Classification doesn't need deep reasoning; low effort keeps latency and cost down.
                # (Passed via extra_body because the pinned SDK predates the output_config kwarg.)
                extra_body={"output_config": {"effort": "low"}},
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_data
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            )
        except anthropic.APIError as e:
            raise Exception(f"Claude API call failed: {e}")

        if message.stop_reason == "refusal":
            raise Exception("Claude declined to classify this image")

        # The response can include thinking blocks before the text answer
        text = next((block.text for block in message.content if block.type == "text"), None)
        if text is None:
            raise Exception(f"Claude returned no text (stop_reason={message.stop_reason})")
        return text

    def _parse_claude_response(self, response: str) -> Dict:
        """Parse Claude's JSON response."""
        try:
            # Clean up response if needed
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:]
            if response.endswith('```'):
                response = response[:-3]
            
            return json.loads(response)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response: {e}")
            logger.error(f"Raw response: {response}")
            
            # Fallback: try to extract basic info
            return {
                'items': [
                    {
                        'category': 'clothing',
                        'confidence': 0.5,
                        'colors': ['Unknown'],
                        'color_hexes': ['#808080'],
                        'primary_color': 'Unknown'
                    }
                ],
                'primary_category': 'clothing',
                'overall_colors': ['Unknown'],
                'confidence': 0.5
            }


# Django view for the API endpoint (alternative to the YOLOS-based detector)
@login_required
@require_http_methods(["POST"])
def claude_fashion_detection_api(request):
    """API endpoint for Claude-based fashion detection."""
    try:
        if 'image' not in request.FILES:
            return JsonResponse({'error': 'No image provided'}, status=400)
        
        image_file = request.FILES['image']
        
        # Validate image
        if not image_file.content_type.startswith('image/'):
            return JsonResponse({'error': 'Invalid image format'}, status=400)
        
        # Initialize detector
        detector = ClaudeFashionDetector()
        
        # Perform detection
        results = detector.detect_fashion_objects(image_file)
        
        return JsonResponse(results)
        
    except Exception as e:
        logger.error(f"Fashion detection API error: {e}")
        return JsonResponse({
            'error': f'Detection failed: {str(e)}',
            'detected_objects': [],
            'detection_method': 'claude_vision_api_error'
        }, status=500)
