"""Marketplace listing creation, category taxonomy APIs and fashion detection."""

import logging

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render

from rest_framework import status, generics, permissions
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response

from ..fashion_taxonomy import fashion_taxonomy, FASHION_TAXONOMY
from ..models import Category, MarketplaceItem, MarketplaceItemImage, TempImage
from ..serializers import MarketplaceItemSerializer, CategorySerializer

logger = logging.getLogger(__name__)


def get_fashion_service():
    """Load the computer-vision detector lazily; it pulls in torch and transformers."""
    from ..listings.smart_fashion_detection import get_fashion_service as _get_fashion_service
    return _get_fashion_service()

@login_required
def create_listing_view(request):
    """Render the upload listing page with fashion taxonomy data."""
    # Simplified frontend data - just what's needed for basic operations
    frontend_data = {
        'detection_mappings': fashion_taxonomy.detection_mappings,
        'category_names': list(fashion_taxonomy.top_level_categories.keys()),
    }

    context = {
        'fashion_data': frontend_data,
    }
    return render(request, 'listings/create_item.html', context)


def get_category_tree(request):
    """API endpoint to get the full category tree for the dropdown."""
    def format_category_tree():
        """Convert taxonomy to hierarchical structure for UI."""
        tree = []

        for main_category, subcategories in FASHION_TAXONOMY.items():
            if main_category == 'accessories':
                # Handle accessories specially since jewelry is nested
                tree.append({
                    'id': 'accessories',
                    'name': 'Accessories',
                    'path': 'accessories',
                    'children': []
                })

                # Add jewelry as a separate top-level category
                if 'jewelry' in subcategories:
                    jewelry_children = []
                    for jewelry_type, items in subcategories['jewelry'].items():
                        jewelry_children.append({
                            'id': f'accessories.jewelry.{jewelry_type}',
                            'name': format_category_name(jewelry_type),
                            'path': f'accessories.jewelry.{jewelry_type}',
                            'children': [
                                {
                                    'id': f'accessories.jewelry.{jewelry_type}.{item}',
                                    'name': format_category_name(item),
                                    'path': f'accessories.jewelry.{jewelry_type}.{item}',
                                    'children': []
                                } for item in (items if isinstance(items, list) else [])
                            ] if isinstance(items, list) else []
                        })

                    tree.append({
                        'id': 'jewelry',
                        'name': 'Jewelry',
                        'path': 'accessories.jewelry',
                        'children': jewelry_children
                    })

                # Add other accessories
                for acc_type, items in subcategories.items():
                    if acc_type != 'jewelry':
                        acc_children = []
                        if isinstance(items, list):
                            acc_children = [
                                {
                                    'id': f'accessories.{acc_type}.{item}',
                                    'name': format_category_name(item),
                                    'path': f'accessories.{acc_type}.{item}',
                                    'children': []
                                } for item in items
                            ]

                        # Find the accessories entry and add this subcategory
                        accessories_entry = next((cat for cat in tree if cat['id'] == 'accessories'), None)
                        if accessories_entry:
                            accessories_entry['children'].append({
                                'id': f'accessories.{acc_type}',
                                'name': format_category_name(acc_type),
                                'path': f'accessories.{acc_type}',
                                'children': acc_children
                            })

            else:
                # Handle other main categories
                top_level_name = {
                    'clothing': 'Clothing',
                    'shoes': 'Shoes',
                    'bags': 'Bags & Purses',
                    'intimates': 'Loungewear & Lingerie'
                }.get(main_category, format_category_name(main_category))

                children = []
                for sub_category, items in subcategories.items():
                    sub_children = []

                    if isinstance(items, dict):
                        # Handle nested structure like clothing.tops.blouses
                        for specific_type, specific_items in items.items():
                            specific_children = []
                            if isinstance(specific_items, list):
                                specific_children = [
                                    {
                                        'id': f'{main_category}.{sub_category}.{specific_type}.{item}',
                                        'name': format_category_name(item),
                                        'path': f'{main_category}.{sub_category}.{specific_type}.{item}',
                                        'children': []
                                    } for item in specific_items
                                ]

                            sub_children.append({
                                'id': f'{main_category}.{sub_category}.{specific_type}',
                                'name': format_category_name(specific_type),
                                'path': f'{main_category}.{sub_category}.{specific_type}',
                                'children': specific_children
                            })

                    elif isinstance(items, list):
                        # Handle simple list like shoes.heels
                        sub_children = [
                            {
                                'id': f'{main_category}.{sub_category}.{item}',
                                'name': format_category_name(item),
                                'path': f'{main_category}.{sub_category}.{item}',
                                'children': []
                            } for item in items
                        ]

                    children.append({
                        'id': f'{main_category}.{sub_category}',
                        'name': format_category_name(sub_category),
                        'path': f'{main_category}.{sub_category}',
                        'children': sub_children
                    })

                tree.append({
                    'id': main_category,
                    'name': top_level_name,
                    'path': main_category,
                    'children': children
                })

        return tree

    def format_category_name(name):
        """Convert snake_case to readable format."""
        return name.replace('_', ' ').replace('-', ' ').title()

    try:
        tree = format_category_tree()
        return JsonResponse({
            'success': True,
            'categories': tree
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


def search_categories(request):
    """API endpoint to search categories."""
    query = request.GET.get('q', '').lower().strip()

    if not query or len(query) < 2:
        return JsonResponse({
            'success': True,
            'results': []
        })

    def search_in_taxonomy(taxonomy, parent_path=''):
        """Recursively search taxonomy for matching categories."""
        results = []

        for key, value in taxonomy.items():
            current_path = f"{parent_path}.{key}" if parent_path else key

            # Check if current key matches
            formatted_name = key.replace('_', ' ').replace('-', ' ').title()
            if query in key.lower() or query in formatted_name.lower():
                results.append({
                    'id': current_path,
                    'name': formatted_name,
                    'path': current_path,
                    'type': 'category'
                })

            # Search in nested structures
            if isinstance(value, dict):
                results.extend(search_in_taxonomy(value, current_path))
            elif isinstance(value, list):
                for item in value:
                    item_path = f"{current_path}.{item}"
                    item_name = item.replace('_', ' ').replace('-', ' ').title()
                    if query in item.lower() or query in item_name.lower():
                        results.append({
                            'id': item_path,
                            'name': item_name,
                            'path': item_path,
                            'type': 'item'
                        })

        return results

    try:
        results = search_in_taxonomy(FASHION_TAXONOMY)

        # Limit results and sort by relevance
        results = sorted(results, key=lambda x: (
            0 if query in x['name'].lower() else 1,  # Exact matches first
            len(x['name']),  # Shorter names first
            x['name'].lower()  # Alphabetical
        ))[:20]

        return JsonResponse({
            'success': True,
            'results': results
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


def get_category_breadcrumb(request):
    """API endpoint to get breadcrumb for a category path."""
    path = request.GET.get('path', '')

    if not path:
        return JsonResponse({
            'success': True,
            'breadcrumb': []
        })

    def format_category_name(name):
        """Convert snake_case to readable format."""
        return name.replace('_', ' ').replace('-', ' ').title()

    try:
        parts = path.split('.')
        breadcrumb = []

        for i, part in enumerate(parts):
            breadcrumb.append({
                'name': format_category_name(part),
                'path': '.'.join(parts[:i+1])
            })

        return JsonResponse({
            'success': True,
            'breadcrumb': breadcrumb
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
def select_detected_items(request):
    """Screen to select detected objects to create item listings"""
    return render(request, 'listings/select_detected_items.html')


class MarketplaceItemCreateAPIView(generics.CreateAPIView):
    """Enhanced API endpoint for creating marketplace items with fashion detection."""
    queryset = MarketplaceItem.objects.all()
    serializer_class = MarketplaceItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def create(self, request, *args, **kwargs):
        """Enhanced create with fashion detection and image processing."""
        logger.info(f"📥 Creating listing for user: {request.user.username}")

        # Handle multiple image uploads
        images = []
        image_count = 0

        # Collect all uploaded images
        while f'image_{image_count}' in request.FILES:
            images.append(request.FILES[f'image_{image_count}'])
            image_count += 1

        logger.info(f"📷 Found {len(images)} images")

        # Process the first image for fashion detection if available
        detection_results = {}
        enhanced_data = request.data.copy()

        if images:
            primary_image = images[0]
            logger.info(f"🔍 Running fashion detection on: {primary_image.name}")

            fashion_service = get_fashion_service()
            detection_results = fashion_service.detect_fashion_objects(primary_image)

            # Log detection results
            if not detection_results.get('error'):
                logger.info(f"✨ Detected category: {detection_results.get('primary_category')}")

                context_info = detection_results.get('context_analysis', {})
                logger.info(f"🧠 Detected context: {context_info.get('detected_context', 'unknown')}")
                logger.info(f"📊 Objects found: {detection_results.get('total_objects', 0)}")
            else:
                logger.warning(f"Detection failed: {detection_results.get('error')}")

        # Create the item
        serializer = self.get_serializer(data=enhanced_data)
        serializer.is_valid(raise_exception=True)
        item = serializer.save(seller=request.user)

        logger.info(f"📦 Created item: {item.title} (ID: {item.item_id})")

        # Process and save images
        if images:
            self._process_and_save_images(item, images, request.data)

        # Prepare response with detection results
        response_data = serializer.data
        response_data['detection_results'] = detection_results

        headers = self.get_success_headers(response_data)
        return Response(
            response_data,
            status=status.HTTP_201_CREATED,
            headers=headers
        )

    def _map_yolos_to_category(self, yolos_category):
        """Map YOLOS-Fashionpedia categories to your Category model."""
        fashion_service = get_fashion_service()
        mapped_name = fashion_service.map_category_to_django(yolos_category)

        try:
            category, created = Category.objects.get_or_create(
                name=mapped_name,
                defaults={'slug': mapped_name.lower().replace(' ', '-')}
            )
            if created:
                logger.info(f"📁 Created new category: {mapped_name}")
            return category
        except Exception as e:
            logger.error(f"Category mapping error: {e}")
            return None

    def _process_and_save_images(self, item, images, form_data):
        """Process images with auto-crop/enhance and save."""
        auto_crop = form_data.get('auto_crop') == 'true'
        auto_enhance = form_data.get('auto_enhance') == 'true'

        logger.info(f"🖼️ Processing {len(images)} images (crop: {auto_crop}, enhance: {auto_enhance})")

        fashion_service = get_fashion_service()

        for index, image_file in enumerate(images):
            try:
                # Use the detector's preprocessing for auto-crop/enhance
                if auto_crop or auto_enhance:
                    # Analyze image context for better preprocessing
                    analysis = fashion_service.detector.analyze_image_context(image_file)
                    processed_image = fashion_service.detector.preprocess_image(image_file, analysis.context)
                else:
                    image_file.seek(0)
                    processed_image = image_file

                # Upload to S3 (if you have S3 upload functionality)
                # object_name = f"marketplace/{item.item_id}/{index}_{image_file.name}"
                # s3_url = fashion_service.upload_to_s3(processed_image, object_name)

                # For now, use local storage
                image_url = f"marketplace/{item.item_id}_{index}_{image_file.name}"
                logger.info(f"💾 Using path: {image_url}")

                MarketplaceItemImage.objects.create(
                    item=item,
                    image=image_url,
                    is_primary=(index == 0),
                    order=index,
                    alt_text=f"{item.title} - Image {index + 1}"
                )

                logger.info(f"✅ Saved image {index + 1}: {image_file.name}")

            except Exception as e:
                logger.error(f"Image processing error for {image_file.name}: {e}")


class MarketplaceItemListAPIView(generics.ListAPIView):
    """API endpoint for listing marketplace items with enhanced filtering."""
    queryset = MarketplaceItem.objects.filter(is_active=True)
    serializer_class = MarketplaceItemSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category__slug=category)

        # Filter by detected attributes
        detected_type = self.request.query_params.get('detected_type')
        if detected_type:
            queryset = queryset.filter(
                attributes__attribute__name='Detected Item Type',
                attributes__attribute__value=detected_type
            ).distinct()

        # Filter by price range
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)

        # Search in title and description
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(brand__icontains=search) |
                Q(color__icontains=search)
            )

        return queryset


class CategoryListAPIView(generics.ListAPIView):
    """API endpoint for listing categories."""
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]

class FashionDetectionTestAPIView(generics.GenericAPIView):
    """API endpoint for testing fashion detection on uploaded images."""
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        """Test fashion detection on uploaded image(s)."""
        try:
            images = []
            image_ids = []

            # Check for multiple images with indexed names
            image_count = 0
            while f'image_{image_count}' in request.FILES:
                images.append(request.FILES[f'image_{image_count}'])
                # Get the corresponding image_id if provided
                image_id = request.POST.get(f'image_id_{image_count}')
                image_ids.append(image_id)
                image_count += 1

            # Fallback to single image if no indexed images found
            if not images and 'image' in request.FILES:
                images = [request.FILES['image']]
                image_id = request.POST.get('image_id')
                image_ids = [image_id] if image_id else [None]

            if not images:
                return Response({'error': 'No image(s) provided'}, status=status.HTTP_400_BAD_REQUEST)

            # Get TempImage URLs for frontend use (with error handling)
            temp_image_urls = []
            for image_id in image_ids:
                if image_id:
                    try:
                        temp_img = TempImage.objects.get(id=image_id)
                        temp_image_urls.append({
                            'id': str(temp_img.id),
                            'url': temp_img.image.url
                        })
                    except TempImage.DoesNotExist:
                        logger.warning(f"TempImage with id {image_id} not found")
                        temp_image_urls.append(None)
                else:
                    temp_image_urls.append(None)

            # Get fashion service
            fashion_service = get_fashion_service()

            # Single image - existing behavior
            if len(images) == 1:
                results = fashion_service.detect_fashion_objects(images[0])
                # Add temp image URL if available
                if temp_image_urls[0]:
                    results['temp_image_ref'] = temp_image_urls[0]
                return Response(results, status=status.HTTP_200_OK)

            # Multiple images - new behavior
            all_detections = []
            image_results = []

            for idx, image_file in enumerate(images):
                results = fashion_service.detect_fashion_objects(image_file)
                image_results.append(results)

                if not results.get('error'):
                    # Add source image index to each detection
                    for obj in results.get('detected_objects', []):
                        obj['source_image_index'] = idx
                        # Add the TempImage URL reference if available
                        if idx < len(temp_image_urls) and temp_image_urls[idx]:
                            obj['source_image_id'] = temp_image_urls[idx]['id']
                            obj['source_image_url'] = temp_image_urls[idx]['url']
                        all_detections.append(obj)

            # Identify unique items across all images
            unique_items = self._identify_unique_items(all_detections)

            return Response({
                'detected_objects': unique_items,  # For compatibility
                'all_detections': all_detections,
                'unique_items': unique_items,
                'temp_image_refs': temp_image_urls,  # Return TempImage references
                'image_results': image_results,
                'total_images': len(images),
                'total_detections': len(all_detections),
                'total_unique': len(unique_items),
                'is_multi_image': True
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Fashion detection error: {e}")
            return Response(
                {'error': f'Detection failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _identify_unique_items(self, all_detections):
        """Identify unique items across multiple detections."""
        if not all_detections:
            return []

        unique_items = []

        for detection in all_detections:
            is_duplicate = False

            for unique in unique_items:
                # Check if this is the same item type
                if self._are_items_similar(detection, unique):
                    is_duplicate = True

                    # Only update confidence, NOT the bounding box or source image
                    # Keep the FIRST occurrence's bounding box and source
                    if detection['confidence'] > unique['confidence']:
                        # Just update the confidence, not the whole detection
                        unique['confidence'] = detection['confidence']

                    # Track ALL source images that contain this item
                    if 'source_images' not in unique:
                        unique['source_images'] = [unique.get('source_image_index', 0)]
                    if detection['source_image_index'] not in unique['source_images']:
                        unique['source_images'].append(detection['source_image_index'])
                    break

            if not is_duplicate:
                # For new unique items, preserve ALL original detection info
                detection['source_images'] = [detection.get('source_image_index', 0)]
                # Ensure we keep the correct source image URL/ID
                unique_items.append(detection.copy())  # Use copy to avoid reference issues

        return unique_items

    def _are_items_similar(self, item1, item2):
        """Determine if two detected items are the same object."""
        # Same category is required
        if item1['category'] != item2['category']:
            return False

        # Get colors
        color1 = item1.get('primary_color', 'Unknown')
        color2 = item2.get('primary_color', 'Unknown')

        # For certain items, be more strict
        if item1['category'] in ['shoe', 'bag, wallet', 'belt', 'watch']:
            # Accessories need exact color match
            return color1 == color2

        # For clothing, allow similar colors
        return self._colors_are_similar(color1, color2)

    def _colors_are_similar(self, color1, color2):
        """Check if two color names represent similar colors."""
        if color1 == color2:
            return True

        similar_groups = [
            ['White', 'Off-White', 'Light Gray'],
            ['Black', 'Charcoal', 'Dark Gray', 'Navy'],
            ['Brown', 'Tan', 'Khaki', 'Beige'],
            ['Blue', 'Navy', 'Denim', 'Royal Blue'],
            ['Gray', 'Light Gray', 'Dark Gray'],
            ['Red', 'Burgundy', 'Maroon', 'Wine'],
            ['Green', 'Forest Green', 'Olive', 'Hunter Green'],
        ]

        for group in similar_groups:
            if color1 in group and color2 in group:
                return True
        return False
