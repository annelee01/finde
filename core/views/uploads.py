"""Temporary image uploads used while creating a listing."""

import logging
import os
import uuid
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

import boto3
from PIL import Image

from ..models import TempImage

logger = logging.getLogger(__name__)


@require_http_methods(["POST"])
def upload_temp_image(request):
    """Handle initial image upload and store as TempImage"""
    if request.method == 'POST' and request.FILES.get('image'):
        # Get or create session
        if not request.session.session_key:
            request.session.create()

        session_key = request.session.session_key
        batch_id = request.POST.get('batch_id', str(uuid.uuid4()))

        try:
            # Process and save ONLY the working copy
            working_image = create_working_image(
                request.FILES['image'],
                session_key,
                batch_id
            )

            return JsonResponse({
                'success': True,
                'image_id': str(working_image.id),
                'working_url': working_image.image.url,
                'batch_id': batch_id
            })
        except Exception as e:
            logger.exception(f"Error in upload_temp_image: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

    return JsonResponse({'success': False, 'error': 'No image provided'}, status=400)

def create_working_image(uploaded_file, session_key, batch_id):
    """Optimized for iPhone/mobile uploads to marketplace"""

    img = Image.open(uploaded_file)

    # iPhone images are often HEIC, ensure compatibility
    if img.mode not in ('RGB', 'RGBA'):
        img = img.convert('RGB')

    # Two-tier sizing strategy for marketplace
    # Full size for detail view: 1600px (enough for zoom)
    # This handles 4K displays while keeping files manageable
    max_dimension = 1600

    # Only downsize if larger
    if max(img.size) > max_dimension:
        img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

    output = BytesIO()

    # WebP with higher quality for marketplace
    # 90 quality preserves iPhone photo detail while still achieving 40-50% compression
    try:
        img.save(output,
                format='WEBP',
                quality=90,  # Higher quality for product photos
                method=6)    # Max compression effort
        file_extension = 'webp'
    except:
        # JPEG fallback with high quality
        output = BytesIO()
        img.save(output,
                format='JPEG',
                quality=92,  # High quality for fallback
                optimize=True,
                progressive=True,
                subsampling=0)  # Preserve color detail
        file_extension = 'jpg'

    output.seek(0)

    # Create filename
    base_name = os.path.splitext(uploaded_file.name)[0]
    filename = f'listing_{base_name}.{file_extension}'

    temp_image = TempImage.objects.create(
        session_key=session_key,
        batch_id=batch_id,
        image=ContentFile(output.read(), name=filename),
        metadata={
            'type': 'working',
            'original_filename': uploaded_file.name,
            'original_size': uploaded_file.size,
            'optimized_size': output.tell(),
            'dimensions': img.size,
            'savings_percent': round((1 - output.tell()/uploaded_file.size) * 100, 1)
        }
    )

    return temp_image

# Cancel action in create listing to remove session image data
@require_http_methods(["POST"])
def clear_listing_session(request):
    """Delete all temp images and clear session data when user cancels"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)

    try:
        # Get session key
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key

        # Begin transaction for atomic operation
        with transaction.atomic():
            # Get all temp images for this session
            temp_images = TempImage.objects.filter(session_key=session_key)

            # Delete S3 objects if using S3
            s3_client = None
            if hasattr(settings, 'AWS_STORAGE_BUCKET_NAME'):
                s3_client = boto3.client(
                    's3',
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    region_name=settings.AWS_S3_REGION_NAME
                )

                # Delete each image from S3
                for temp_image in temp_images:
                    if temp_image.image:
                        try:
                            # Extract key from URL or use the image field name
                            key = str(temp_image.image.name)
                            s3_client.delete_object(
                                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                                Key=key
                            )
                            logger.debug(f"Deleted S3 object: {key}")
                        except Exception as e:
                            logger.error(f"Error deleting S3 object {key}: {str(e)}")

            # Delete database records
            deleted_count = temp_images.count()
            temp_images.delete()

            # Clear any session data related to listings
            keys_to_remove = [
                'listings', 'current_batch', 'upload_session',
                'detection_results', 'selected_items'
            ]
            for key in keys_to_remove:
                if key in request.session:
                    del request.session[key]

            # Save session changes
            request.session.save()

            return JsonResponse({
                'success': True,
                'message': f'Cleared {deleted_count} temp images and session data',
                'deleted_count': deleted_count
            })

    except Exception as e:
        logger.exception(f"Error in clear_listing_session: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
