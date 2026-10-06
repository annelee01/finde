"""Admin tools for importing eBay listings: size/attribute extraction, image conversion, curation."""

import json
import logging
import os
import re
import time
from datetime import datetime
from io import BytesIO

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

import requests
import pytz
from PIL import Image

from ..decorators import admin_required
from ..maps_and_terms import (
    REGEX_PATTERNS,
    EXCLUDED_TERMS,
    WAIST_TERMS,
    TOPS_TERMS,
    BOTTOMS_TERMS,
    LINGERIE_TERMS,
    BOTTOMS_CATEGORY_IDS,
    SKIRT_CATEGORY_IDS,
    SIZE_ABBR_MAP,
    SHOE_CATEGORY_IDS,
    SHOE_TERMS,
    HAT_CATEGORY_IDS,
    HAT_SIZE_MAP,
)
from ..models import CoreEbayitem, CoreEbayitemSold, Timestamp, ShoeSizeConversion
from ..size_sorting import (
    extract_size_from_aspect,
    extract_size_to_process,
    extract_chest_from_size_aspect,
    extract_waist_from_size_aspect,
    normalize_size_value,
    is_valid_size,
)
from ..utils import (
    VALID_COLORS,
    normalize_single_color,
    get_item_color,
    create_categories,
    CATEGORY_MAPPINGS,
)
from finde.ebay_search import search_ebay_items, get_item_details
from finde.find_relistedItemId import check_item_availability

logger = logging.getLogger(__name__)


ebay_env = settings.EBAY_ENV

# converts item image to webp to save file size
def convert_image_to_webp(image_url, title, force_overwrite=False):
    # Sanitize the title to create a valid filename
    sanitized_title = re.sub(r'[<>:"/\\|?*#%&@]', '', title or '')  # Remove invalid characters
    sanitized_title = re.sub(r'\s+', '_', sanitized_title)          # Replace spaces with underscores
    sanitized_title = re.sub(r'[^a-zA-Z0-9_\-.]', '', sanitized_title)  # Keep safe chars
    if not sanitized_title:
        sanitized_title = 'default_image'

    relative_path = f'webp_images/{sanitized_title}.webp'  # e.g., webp_images/my_image.webp

    # Add image cache busting when force_overwrite is True to make sure the image actually updates, adding a unique timestamp to the end of the URL
    if force_overwrite:
        # Option 1: Add timestamp
        timestamp = int(time.time())
        filename = f'{sanitized_title}_{timestamp}.webp'

    else:
        filename = f'{sanitized_title}.webp'

    relative_path = f'webp_images/{filename}'

    # Download original image
    response = requests.get(image_url)
    response.raise_for_status()
    image = Image.open(BytesIO(response.content))

    # Resize for thumbnails, to exactly 600px height, width varies proportionally
    # Only downscale large images above 600px in height - don't upscale small images (less than 600px in height) to avoid quality loss
    original_width, original_height = image.size
    if original_height > 600:
        new_width = int((original_width * 600) / original_height)
        image = image.resize((new_width, 600), Image.Resampling.LANCZOS)

    # Convert image to WebP in memory
    webp_image_io = BytesIO()
    image.save(webp_image_io, format='WebP', quality=75, method=6)
    webp_image_io.seek(0)

    if ebay_env == 'sandbox':
        # Save locally
        full_path = os.path.join(settings.MEDIA_ROOT, relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'wb') as f:
            f.write(webp_image_io.read())
    else:
        # When force_overwrite is True, we're creating a new filename
        # so no need to delete the old one in this approach
        if force_overwrite:
            # The new timestamped filename ensures cache busting
            pass
        elif default_storage.exists(relative_path):
            # If not force overwriting and file exists, don't recreate
            return relative_path

        # Save new image to AWS S3
        default_storage.save(relative_path, webp_image_io)

    return relative_path  # Returns 'webp_images/filename_timestamp.webp' when force_overwrite=True


@transaction.atomic
@admin_required
def save_selected_items(request):

    # save joined sizes in order from smallest to largest
    def get_size_order(size):
        """Return a numeric value for sorting sizes from smallest to largest"""
        size_order = {
            'XXXS': 1, 'XXS': 2, 'XS': 3, 'S': 4, 'SM': 5, 'M': 6, 'MED': 7,
            'L': 8, 'XL': 9, 'XXL': 10, 'XXXL': 11, '2XL': 10, '3XL': 11,
            # Add numeric sizes
            '0': 0, '2': 2, '4': 4, '6': 6, '8': 8, '10': 10, '12': 12, '14': 14, '16': 16, '18': 18, '20': 20
        }

        # Handle numeric sizes that might not be in the map
        if size.isdigit():
            return int(size)

        return size_order.get(size.upper(), 999)

    if request.method == 'POST':
        try:
            # Print the raw content of request.body

            # Parse the item IDs from the request body
            items_data = json.loads(request.body)
            item_ids = [item['itemId'] for item in items_data if 'itemId' in item]


            timestamp = Timestamp.objects.create()
            new_items = []

            # Validate that the item_ids is a list
            if not isinstance(items_data, list):
                return JsonResponse({'error': 'Expected a list of item IDs'}, status=400)

            for item_id in item_ids:
                # Check if an item with the same item_id already exists
                if not CoreEbayitem.objects.filter(item_id=item_id).exists():
                    # Fetch item details including availability status
                    item_details = get_item_details(item_id)


                    logger.debug('item_id in save_selected_items %s', item_id)
                    # Call the function to check item availability
                    item_availability = check_item_availability(item_id)
                    # Extract the availability status from the result

                    # Set default for sandbox environment
                    if settings.EBAY_ENV == 'sandbox':
                        availability_status = 'IN_STOCK'
                        logger.debug(f"Sandbox mode: Defaulting availability_status to IN_STOCK for item {item_id}")
                    else:
                        availability_status = item_availability.get('availability_status')

                    itemEndDate = item_availability.get('itemEndDate', 'Unknown') # NOTE most items dont have an 'itemenddate', so they wont return in the api response

                    itemCreationDate = item_details.get('itemCreationDate', 'Unknown')

                    color = get_item_color(item_details)
                    normalized_single_color = normalize_single_color(color)


                    # Reassign "modern" category id and/or consolidate categories to save under "vintage" category id instead
                    category_id = item_details.get('categoryId')

                    if category_id == "169291": # Reassign "modern" purse category id to save under "vintage" category id instead
                        category_id = "74962"   # vtg purses
                    if category_id == "45258":  # mod Wallets & Coin Purses
                        category_id = "175769"  # vtg Wallets & Coin Purses
                    if category_id == "45230":  # mod hat
                        category_id = "74969"   # vtg hat
                    if category_id == "163619":  # vtg men's hat
                        category_id = "74969"   # vtg hat
                    if category_id == "179247": # mod womens Sunglasses & Sunglasses Accessories
                        category_id = "48559"  # vtg sunglasses
                    if category_id == "180957": # mod eyeglass frames
                        category_id = "175805"  # vtg eyeglasses
                    if category_id == "67670": # mod reading eyeglasses
                        category_id = "175805"  # vtg eyeglasses
                    if category_id == "45220":  # mod hair accessories
                        category_id = "175819"  # vtg hair accessories
                    if category_id == "45238":  # mod scarves
                        category_id = "175807"  # vtg scarves
                    if category_id == "3003":   # mod belts
                        category_id = "163601"  # vtg belts
                    if category_id == "63861":  # mod dresses
                        category_id = "175784"  # vtg dresses
                    if category_id == "53159":  # mod tops (women's)
                        category_id = "175795"  # vtg tops
                    if category_id == "63864":  # mod skirts (women's)
                        category_id = "175791"  # vtg skirts
                    if category_id == "63863":  # mod pants (women's)
                        category_id = "175796"  # vtg pants
                    if category_id == "11554":  # mod jeans (women's)
                        category_id = "175785"  # vtg jeans
                    if category_id == "3009":  # mod jumpsuits & rompers (women's)
                        category_id = "175787"  # vtg jumpsuits & playsuits
                    if category_id == "63866":  # mod sweaters (women's)
                        category_id = "175786"  # vtg sweaters
                    if category_id == "63862":  # mod coats, jackets & vests (women's)
                        category_id = "175783"  # vtg coats, jackets & vests
                    if category_id == "63865":  # mod suits & suit separates (women's)
                        category_id = "175792"  # vtg suits, sets & suit separates
                    if category_id == "262014":  # Rings (modern)
                        category_id = "48447"   # Vintage rings
                    if category_id == "261994":  # Rings (women's, mod)
                        category_id = "48447"   # Vintage rings
                    if category_id == "261988":  # Fine Bracelets & Charms (mod)
                        category_id = "262003"   # Vintage & Antique Bracelets & Charms
                    if category_id == "261987":  # Fashion Bracelets & Charms (mod)
                        category_id = "262003"   # Vintage & Antique Bracelets & Charms
                    if category_id == "261993":  # Fine Necklaces & Pendants (mod)
                        category_id = "262013"   # Vintage & Antique Necklaces & Pendants
                    if category_id == "110655":  # Handcrafted Necklaces & Pendants
                        category_id = "262013"    # Vintage & Antique Necklaces & Pendants

                    foot_length_in = None
                    us_shoe_size = None
                    shoe_size_width = None
                    europe_shoe_size = None
                    uk_shoe_size = None
                    france_shoe_size = None
                    japan_shoe_size = None
                    korea_china_shoe_size = None

                    hat_size = None
                    chest_size = None
                    bra_size = None
                    cup_size = None
                    band_size = None
                    waist_size = None
                    inseam = None
                    hip_size = None
                    waist_to_hem = None
                    shoulder_to_shoulder = None
                    shoulder_to_hem = None
                    women_size = None
                    size = None
                    bottoms_size = None
                    ring_size = None
                    necklace_length = None
                    item_length = None
                    material = None
                    brand = 'Vintage' # Default for unbranded items or no brand given in aspect
                    seller_username = item_details.get('seller', {}).get('username', 'Unknown')

                    # Add inches symbol to size values from title extraction
                    def add_inches_to_sizes(size_str):
                        """Add inch symbols to sizes in a string or list."""
                        logger.debug('adding inches to %s', size_str)
                        if not size_str:  # Handle None or empty inputs
                            logger.debug('empty string, returning ""')
                            return ""

                        # If size_str is a list, join the list into a string and process it
                        if isinstance(size_str, list):
                            logger.debug('size_str is a list %s', size_str)
                            # Convert integers to strings before joining
                            size_str = [str(size) for size in size_str]  # Convert to string
                            size_str = " ".join(size_str)  # Now join them

                        # If size_str is a string, proceed with the current logic
                        if isinstance(size_str, str):
                            logger.debug('size_str is a str %s', size_str)
                            # Normalize curly quotes to straight quotes
                            size_str = size_str.replace("”", "\"").replace("“", "\"")

                            # Split the size string into individual values and add inches if missing
                            sizes = size_str.split()
                            logger.debug('size_str split sizes %s', sizes)

                            # Extract numeric values with optional decimals using regex
                            numeric_matches = REGEX_PATTERNS["numeric_plain_pattern"].findall(size_str)
                            logger.debug('Numeric matches: %s', numeric_matches)

                            sizes_with_inches = [f"{size}\"" if not size.endswith('\"') else size for size in numeric_matches]
                            logger.debug('sizes_with_inches %s', sizes_with_inches)

                            # Return the sizes as a single string with space separation
                            return " ".join(sizes_with_inches)

                        # If the size_str is a number (either integer or float decimal), add inches symbol
                        if isinstance(size_str, (int, float)):
                            return f"{size_str}\""

                    # Initialize an empty list to store size/size_women from the aspect
                    sizes_list_from_aspect = []

                    # First, try to extract size information from aspects
                    for aspect in item_details.get('localizedAspects', []):
                        name = aspect.get('name')
                        title = item_details.get('title', '').lower()
                        value = aspect.get('value').replace('"', '').replace("'", '').replace('N/A', '').replace('NA', '').strip() # Remove quotes and trim spaces
                        # skip further processing if the item aspect value is invalid, like '

                        logger.debug(f'value extracted: {value}, name: {name}')

                        if "Shoe Size" in name and any(term in title for term in SHOE_TERMS): # This works for US Shoe Size (Women's) or US Shoe Size (Men's)
                            extraction_result = extract_size_from_aspect(name, value)

                            # Handle insufficient return values by setting defaults
                            if not extraction_result or len(extraction_result) < 2:
                                logger.warning(f"Size extraction failed for {name}={value} - insufficient return values")
                                result = False
                                converted_sizes_tuple = ((),)  # Tuple containing empty tuple
                                extra_values = []
                            else:
                                result, converted_sizes_tuple, *extra_values = extraction_result

                            # Debug: Print only if conversion failed
                            if not result:
                                logger.warning(f"Size extraction failed for {name}={value}")
                                if extra_values:  # Print extra debug info only if it exists
                                    logger.debug('Debug info: %s', extra_values)
                                continue  # Skip further processing

                            # Extract sizes (cleaner tuple/dict handling)
                            converted_sizes = converted_sizes_tuple[0] if isinstance(converted_sizes_tuple, tuple) else converted_sizes_tuple

                            # Check if converted_sizes is a dictionary
                            if isinstance(converted_sizes, dict):
                                us_shoe_size = converted_sizes.get('us_shoe_size')
                                europe_shoe_size = converted_sizes.get('europe_shoe_size')
                                uk_shoe_size = converted_sizes.get('uk_shoe_size')
                                france_shoe_size = converted_sizes.get('france_shoe_size')
                                japan_shoe_size = converted_sizes.get('japan_shoe_size')
                                korea_china_shoe_size = converted_sizes.get('korea_china_shoe_size')
                                foot_length_in = converted_sizes.get('foot_length_in')

                                # Print all values for debugging
                                logger.debug('US Shoe Size: %s', us_shoe_size)
                                logger.debug('Europe Shoe Size: %s', europe_shoe_size)
                                logger.debug('UK Shoe Size: %s', uk_shoe_size)
                                logger.debug('France Shoe Size: %s', france_shoe_size)
                                logger.debug('Japan Shoe Size: %s', japan_shoe_size)
                                logger.debug('Korea/China Shoe Size: %s', korea_china_shoe_size)
                                logger.debug('Foot Length (inches): %s', foot_length_in)
                            else:
                                logger.warning(f"⚠️ Unexpected format for {name}: {converted_sizes}")


                        if "Bottoms Size" in name:  # This checks for 'Bottoms Size' in the name (women's or men's)
                            extracted_size = extract_size_from_aspect(category_id, value)
                            logger.debug('bottoms size in name %s', extracted_size)

                            if isinstance(extracted_size, tuple):
                                extracted_size = extracted_size[0]

                            logger.debug(f"Initial extracted_size value: {extracted_size}")
                            logger.debug(f"Category ID: {category_id}")
                            logger.debug(f"Is skirt category: {category_id in SKIRT_CATEGORY_IDS}")

                            # Handle skirt categories immediately
                            if category_id in SKIRT_CATEGORY_IDS:
                                size = extracted_size
                                logger.debug(f"Assigned to Size (skirt): {size}")
                                # Don't assign to bottoms_size at all for skirts

                            # Only assign to bottoms_size for non-skirt categories
                            elif category_id in BOTTOMS_CATEGORY_IDS or category_id not in SKIRT_CATEGORY_IDS:
                                logger.debug(f"Category ID {category_id} matches a bottoms category.")

                                # Check if the size is numeric (including float)
                                if bottoms_size and bottoms_size.replace('.', '', 1).isdigit():
                                    numeric_size = float(bottoms_size)
                                    logger.debug('bottoms_size numeric_size: %s', numeric_size)

                                    if numeric_size > 20 and waist_size is None:  # If size is greater than 20, treat as waist size. # only save bottoms_size to waist_size if waist_size doesnt already exist
                                        waist_size = add_inches_to_sizes(bottoms_size)
                                        bottoms_size = None  # Clear bottoms_size to avoid duplicate assignment
                                        logger.debug(f"Reassigned large Bottoms Size {numeric_size} to Waist Size: {waist_size}")
                                    else:
                                        logger.debug(f"Assigned to Bottoms Size: {bottoms_size}")

                                # Check if the size is non-numeric (e.g., "L", "M", "S")
                                elif bottoms_size and bottoms_size.isalpha():  # Only alphabetic characters (non-numeric)
                                    logger.debug(f"Assigned non-numeric Bottoms Size: {bottoms_size}")
                                elif bottoms_size:
                                    bottoms_size = None
                                    logger.warning(f"Invalid Bottoms Size {bottoms_size}, value not assigned.")

                            else:
                                logger.debug(f"NOT a valid pants category (category_id: {category_id})")

                                if isinstance(bottoms_size, (int, float)) and 20.5 <= bottoms_size <= 39.5:
                                    if any(term in item_details['title'].lower() for term in WAIST_TERMS):
                                        waist_size = bottoms_size  # Assign to waist_size
                                        bottoms_size = None  # Clear bottoms_size
                                        logger.debug(f"Assigned bottoms_size to waist_size: {waist_size}")

                                else:
                                    logger.debug(f"NOT a valid pants category (category_id: {category_id} or waist_size)")
                                    if bottoms_size:
                                        # Check for alphabetic sizes (like 'L', 'XL')
                                        # Assign the extracted 'bottoms_size' to 'size' instead, if it's not a bottoms category or waist_size
                                        if isinstance(bottoms_size, str) and bottoms_size.isalpha():
                                            size = bottoms_size.upper()  # Standardize to uppercase for consistency
                                            logger.debug(f"Assigned alphabetical size: {size}")
                                            bottoms_size = None  # IMPORTANT: Clear 'bottoms_size' AFTER size assignment

                                        elif any(term in item_details['title'].lower() for term in WAIST_TERMS):
                                            # If the number is a whole number (like 25.0), convert it to an integer
                                            if isinstance(bottoms_size, str) and bottoms_size.replace('.', '', 1).isdigit():  # First check if value is a number
                                                bottoms_size = float(bottoms_size)  # Convert to float to ensure numerical operations

                                                # Check if the value is effectively a whole number
                                                if bottoms_size.is_integer():  # True if it is like 25.0
                                                    size = int(bottoms_size)  # Convert to integer (removes decimals)
                                                    logger.debug(f"Assigned bottoms_size to bottoms_size (int): {bottoms_size}")
                                                else:
                                                    size = round(bottoms_size, 2)  # Retain decimals, rounded to 2 places if needed
                                                    logger.debug(f"Assigned bottoms_size to bottoms_size (rounded): {bottoms_size}")

                                                if 20.5 <= bottoms_size <= 39.5:
                                                    waist_size = add_inches_to_sizes(bottoms_size)
                                                    logger.debug(f"Reassigned bottoms_size to waist_size: {waist_size}")

                                                # Clear bottoms_size after assigning size or waist_size
                                                bottoms_size = None  # IMPORTANT: Clear 'bottoms_size' after size assignment

                                        # Assign the size to 'size' for non-bottoms items if waist terms are not in title
                                        if not any(term in item_details['title'].lower() for term in WAIST_TERMS):
                                            size = bottoms_size
                                            bottoms_size = None # IMPORTANT Assign 'None' to bottoms_size AFTER size is assigned
                                            logger.debug(f"Assigned bottoms_size to Size: {size}")
                                    else:
                                        logger.warning(f"Invalid size format: {bottoms_size}")

                        # Handle clothing sizes

                        # Hat Size Processing in aspect
                        if name in ("Inside Band Circumference", "Hat Circumference", "unisex_hat_circum", "Head Circumference"):
                            hat_size = extract_size_from_aspect(name, value)  # Extract the size from the aspect
                            logger.debug('Hat Circumference received from aspect: %s', value)

                            hat_size = normalize_size_value(value) # normalized value
                            hat_size = hat_size.replace(" ", "").replace("-", "") # remove spaces and dashes from normalized value
                            logger.debug('Normalized Hat Circumference received from aspect: %s', hat_size)

                            if hat_size in HAT_SIZE_MAP:
                                    logger.debug('hat_size circumference is in HAT_SIZE_MAP: %s', hat_size)
                                    hat_size = HAT_SIZE_MAP[hat_size] + '"'
                                    size = None
                                    logger.debug(f'hat_size assigned from circumberence aspect: {hat_size}')
                            else:
                                hat_size = None

                            logger.debug('Final hat size saved from Circumference aspect: %s', hat_size)


                        if name in ("Size", "Size (Women's)", "Size (Women&amp;amp;apos;s)", "Size (Women&apos;s)") and hat_size is None and category_id not in [
                                "74962",    # Bags, Handbags & Cases
                                "169291",   # Women's Bags & Handbags
                                "175769",   # vtg Wallets & Coin Purses
                                "45258",    # mod Wallets & Coin Purses
                                "48559",    # vtg sunglasses
                                "179247",   # mod womens Sunglasses & Sunglasses Accessories
                                "175805"    # vtg eyeglasses
                            ] and category_id not in SHOE_CATEGORY_IDS: # Dont assign aspect 'size' for shoe items
                            size = extract_size_from_aspect(name, value)  # Extract the size from the aspect
                            logger.debug('Size received from aspect: %s', size)

                            if size is not None:
                                if isinstance(size, tuple):
                                    size = size[0]  # Extract the first element (e.g., 'S' from ('S', None))
                                    logger.debug(f"Extracted size for hat item: {size}")

                                # Append the size to the appropriate list based on the category
                                if category_id in HAT_CATEGORY_IDS:

                                    #IF HAT_SIZE of inches doesnt already exist from extraction of name == "Inside Band Circumference" then
                                    hat_size = extract_size_from_aspect(name, value)  # Extract the size from the aspect
                                    logger.debug('%s %s', f'size for hat_size recieved from aspect:', hat_size)

                                    # Check if hat_size is "one size" (case-insensitive)
                                    if isinstance(hat_size, str) and hat_size.strip().lower() in {"one size", "os"}:
                                        logger.debug("Detected 'one size'. Assigning hat_size and size = None.")
                                        hat_size = None
                                        size = None

                                    if isinstance(hat_size, tuple):
                                        hat_size = hat_size[0]  # Extract the first element (e.g., 'S' from ('S', None))
                                        size = None

                                        if isinstance(hat_size, str) and hat_size.strip().lower() == "one size":
                                            logger.debug("Detected 'one size'. Assigning hat_size and size = None.")
                                            hat_size = None

                                        logger.debug(f"Extracted size for hat item: {hat_size}")

                                    if hat_size in HAT_SIZE_MAP:
                                        logger.debug('hat_size is in HAT_SIZE_MAP: %s', hat_size)
                                        hat_size = HAT_SIZE_MAP[hat_size] + '"'
                                        size = None
                                        logger.debug(f'hat_size assigned from "size" aspect: {hat_size}')
                                    else:
                                        hat_size = None
                                        size = None

                                else:
                                    # For non-hat items, append to sizes_list
                                    sizes_list_from_aspect.append(size)  # Append the size to the sizes list
                                    logger.debug('Sizes extracted from aspect: %s', sizes_list_from_aspect)

                                    # Deduplicate and combine sizes into size
                                    if sizes_list_from_aspect:
                                        # Normalize the size values for consistent comparison and deduplication
                                        normalized_sizes = [str(s) for s in sizes_list_from_aspect]

                                        # Remove duplicates by converting to a set and back to a list
                                        unique_sizes = list(set(normalized_sizes))

                                        # Assign the combined sizes to size for non-hat items
                                        size = ' '.join(unique_sizes)
                                        logger.debug(f"Final combined size: {size}")

                                    else:
                                        size = None  # In case the list is empty

                                    # Ensure chest_size field empty before trying to extract from 'size' aspect field
                                    if chest_size is None:
                                        logger.debug('chest size recieved %s', chest_size)
                                        # Match bra patterns 36B, 36B-36C, excluding decades like 60's, 1920s
                                        bra_matches = REGEX_PATTERNS["bra_pattern"].findall(value)
                                        if bra_matches:
                                            bra_size = extract_chest_from_size_aspect(value)
                                            logger.debug(f"Assigned bra_size from size aspect: {bra_size} from Size, Size (Women's)")
                                        else:
                                            chest_size = add_inches_to_sizes(extract_chest_from_size_aspect(value))
                                            logger.debug(f"Assigned chest_size from size aspect: {chest_size} from Size, Size (Women's)")

                                    # Ensure waist_size field empty before trying to extract from 'size' aspect field
                                    if waist_size is None:
                                        waist_size = extract_waist_from_size_aspect(value)
                                        logger.debug('waist size recieved %s', waist_size)

                        # Other measurements
                        if name == "Chest Size":

                            title = item_details.get('title', '').lower()
                            bra_matches = None

                            if any(term in title for term in LINGERIE_TERMS) and "Loungewear & Lingerie" in CATEGORY_MAPPINGS and not any(excluded_term in title for excluded_term in EXCLUDED_TERMS):
                                bra_matches = REGEX_PATTERNS["bra_pattern"].findall(value)
                                if bra_matches:
                                    bra_size = extract_size_from_aspect(name, value)
                                    bra_size = bra_size.upper()  # Convert bra_size to uppercase
                                    logger.debug(f"Assigned bra_size from aspect: {bra_size} from Chest Size")

                            if not bra_matches:
                                chest_size = extract_size_from_aspect(name, value)
                                logger.debug('extracting chest_size from aspect %s', chest_size)

                                # Extract the first element of the tuple if it's a tuple
                                if isinstance(chest_size, tuple):
                                    chest_size = chest_size[0] if chest_size[0] is not None else ''
                                elif chest_size is None:
                                    chest_size = ''

                                if chest_size.replace('.', '', 1).isdigit():  # Check if it's a valid number (allowing one decimal point)s
                                    chest_size = float(chest_size)
                                    if chest_size < 25: # Double the chest size if it's less than 25
                                        logger.debug(f"Doubling chest size: {chest_size} -> {chest_size * 2}")
                                        chest_size *= 2

                                    if chest_size.is_integer():
                                        chest_size = int(chest_size)  # Convert to integer if it's a whole number
                                    else:
                                        chest_size = round(chest_size, 2)  # Round to 2 decimal places if it's not an integer

                                chest_size = add_inches_to_sizes(chest_size)

                                logger.debug(f"Assigned chest_size from aspect: {chest_size} from Chest Size")

                        if name in ("Intimates & Sleep Size (Women's)", "Intimates & Sleep Size (Women&amp;amp;apos;s)"):
                            logger.debug('Extracted intimates size (raw): %s', value)  # Check what this is returning
                            try:
                                # Attempt to extract numeric part for comparisons (e.g., 38 from "38B")
                                numeric_part = int(''.join(filter(str.isdigit, value)))
                                if 30 <= numeric_part <= 46:  # Numeral bust range
                                    chest_size = add_inches_to_sizes(extract_size_from_aspect(name, value))
                                    logger.debug(f"Assigned chest_size for Intimates & Sleep Size (Women's): {chest_size}")
                                # [skipping a most likely a waist size range for 20-30]
                                elif numeric_part < 20:  # Numeral clothing/dress size range
                                    size = extract_size_from_aspect(name, value)
                                    logger.debug(f"Assigned size for Intimates & Sleep Size (Women's): {size}")
                                else:
                                    logger.debug(f"NO SIZE assigned for Intimates & Sleep Size (Women's): {bra_size}")
                            except ValueError:
                                logger.warning(f"Value '{value}' could not be converted to an integer.")

                                # Handle cases where value is a string and does not contain a numeric part
                                if isinstance(value, str):
                                    # Check if value matches numeric_with_letter_pattern (e.g., "38B", "12L")
                                    if REGEX_PATTERNS["bra_pattern"].findall(value):
                                        bra_size = extract_size_from_aspect(name, value)
                                        logger.debug(f"Assigned {value} to bra_size because it matches the pattern")
                                    else:
                                        normalized_value = normalize_size_value(value) # lowercase values to compare match to SIZE_ABBR_MAP
                                        if normalized_value in SIZE_ABBR_MAP: # If size is a str like 'small', abbreviate into 'S', 'm' to 'M'
                                            size = SIZE_ABBR_MAP[normalized_value]
                                        logger.debug(f"Assigned {size} to size because it does not match the pattern")

                        # BRA Band Size Processing in aspect
                        if name == "Band Size" and '-' in value:
                            logger.debug(f"Band size value before extraction: {value}")

                            # Extract numeric parts as band size range (e.g., "23-30")
                            band_size_range = value.split('-')
                            start_band_size = int(band_size_range[0])  # Extract the start of the range
                            end_band_size = int(band_size_range[1])    # Extract the end of the range

                            # If the range starts with a value less than 30, treat it as a chest size
                            if start_band_size < 30:
                                chest_size = ' '.join(map(lambda x: add_inches_to_sizes(x), range(start_band_size, end_band_size + 1)))
                                logger.debug(f"Band size range starts below 30, assigned to chest_size: {chest_size}")
                            else:
                                bra_size = ' '.join(map(lambda x: add_inches_to_sizes(x), range(start_band_size, end_band_size + 1)))
                                logger.debug(f"Band size range starts from 30 or above, assigned to bra_size: {bra_size}")

                        # Cup Size Processing
                        if name == "Cup Size":
                            logger.debug(f"Cup size value before extraction: {value}")
                            # Match the full bra size pattern (e.g., "34B")
                            bra_matches = REGEX_PATTERNS["numeric_with_letter_pattern"].findall(value)

                            if bra_matches:
                                # Save the full bra size directly
                                bra_size = bra_matches[0]  # Use the first match
                                logger.debug(f"Matched bra pattern. Assigned bra_size: {bra_size}")
                            else:
                                # Extract alphabetic part as cup size (e.g., "B" from "34B")
                                cup_size = ''.join([char for char in value if char.isalpha()])
                                logger.debug(f"Extracted cup size: {cup_size}")
                        # Combine only after both band size and cup size are extracted
                        if bra_size and cup_size:
                            if band_size and cup_size and isinstance(band_size, str) and isinstance(cup_size, str): # Safeguard against None or empty values
                                if band_size in cup_size:
                                    # If the band size is already part of the cup size (e.g., "36B" and "36"), use the full cup size
                                    bra_size = cup_size
                                elif cup_size in band_size:
                                    # If the cup size is already part of the band size (e.g., "36B" and "36"), use the full band size
                                    bra_size = band_size
                                else:
                                    # Otherwise, combine them normally
                                    bra_size = f"{band_size}{cup_size}"

                                logger.debug(f"Combined bra size after checking for duplicates: {bra_size}")

                        if name == "Waist Size":
                            raw_waist_size = extract_size_from_aspect(name, value)
                            logger.debug('Extracted raw waist size: %s', raw_waist_size)

                            # Normalize the input to a list
                            if isinstance(raw_waist_size, str):
                                # Split the string by whitespace into individual sizes
                                waist_size_list = raw_waist_size.split()
                            elif isinstance(raw_waist_size, list):
                                # If it's already a list, use it directly
                                waist_size_list = raw_waist_size
                            else:
                                waist_size_list = []  # Default to an empty list if raw_waist_size is None or invalid

                            logger.debug('Normalized waist_size list: %s', waist_size_list)

                            # Initialize a list to store processed waist sizes
                            processed_waist_sizes = []

                            for waist_size in waist_size_list:
                                # Check if the waist size is a valid numeric value
                                if waist_size.replace('.', '', 1).isdigit():
                                    waist_size = float(waist_size)  # Convert waist size to a float for comparison

                                    if waist_size >= 20:
                                        # If waist size is a whole number, convert it back to an integer
                                        if waist_size.is_integer():
                                            waist_size = int(waist_size)  # Convert to integer if it's a whole number
                                        # Add the waist size as-is if it's valid and >= 20
                                        processed_waist_sizes.append(add_inches_to_sizes(waist_size))
                                        logger.debug('Added waist_size from aspect: %s', waist_size)
                                    else:
                                        # Double the waist size if it's less than 20
                                        doubled_size = waist_size * 2

                                        # Format the doubled size to retain up to 2 decimal places only if needed
                                        if doubled_size.is_integer():
                                            formatted_size = f"{int(doubled_size)}"  # Convert to an integer string for whole numbers
                                        else:
                                            formatted_size = f"{doubled_size:.2f}".rstrip('0').rstrip('.')  # Retain up to 2 decimals for fractional values

                                        processed_waist_sizes.append(add_inches_to_sizes(formatted_size))

                            if processed_waist_sizes:
                                waist_size = ' '.join(processed_waist_sizes)  # Join the valid sizes into a space-separated string
                                logger.debug(f"Assigned to Waist Size List: {waist_size}")
                            else:
                                waist_size = ''  # No valid sizes
                                bottoms_size = waist_size_list if waist_size_list else ''
                                logger.debug(f"No valid waist sizes. Assigned to Bottom Size: {bottoms_size}")


                        if name == "Inseam":
                            title = item_details.get('title', '')
                            if any(term in title for term in BOTTOMS_TERMS):
                                inseam = add_inches_to_sizes(extract_size_from_aspect(name, value))
                                logger.debug('extracted inseam value: %s', inseam)

                        if name == "Hip Size":
                            logger.debug('hip size detected')
                            hip_size = extract_size_from_aspect(name, value)
                            logger.debug('hip size extracted %s', value)
                            # Convert tuple to string if needed
                            if isinstance(hip_size, tuple):
                                hip_size = str(hip_size[0]) if hip_size else None

                            # Check if the hip_size is numeric
                            if hip_size and hip_size.replace('.', '', 1).isdigit(): # Check if it's a valid number (allowing one decimal point)
                                hip_size = float(hip_size)

                                if hip_size < 17:
                                    hip_size = ''
                                    logger.warning(f"Invalid hip size")
                                else:
                                    if 17 <= hip_size <= 30: # Double the hip size if it's in this range
                                        logger.debug(f"Doubling hip size: {hip_size} -> {hip_size * 2}")
                                        hip_size *= 2

                                    # Check for unusually large hip sizes (e.g., > 60 inches), and halve them
                                    if hip_size > 60:  # If the size is greater than a reasonable max hip size, halve it
                                        logger.debug(f"Halving hip size: {hip_size} -> {hip_size / 2}")
                                        hip_size /= 2

                                    if hip_size.is_integer():
                                        hip_size = int(hip_size)  # Convert to integer if it's a whole number
                                    else:
                                        hip_size = round(hip_size, 2)  # Round to 2 decimal places if it's not an integer

                                    hip_size = add_inches_to_sizes(hip_size)

                        if name == "Waist to Hem":
                            waist_to_hem = add_inches_to_sizes(extract_size_from_aspect(name, value))
                        if name == "Shoulder to Shoulder":
                            logger.debug('extracting shoulder to shoulder')
                            shoulder_to_shoulder = add_inches_to_sizes(extract_size_from_aspect(name, value))
                        if name == "Shoulder to Hem":
                            shoulder_to_hem = add_inches_to_sizes(extract_size_from_aspect(name, value))
                        if name == "Ring Size":
                            ring_size = extract_size_from_aspect(name, value)
                        if name == "Necklace Length":
                            necklace_length = add_inches_to_sizes(extract_size_from_aspect(name, value))
                        if name == "Item Length" and category_id in {
                            # restrict to only saving item_length if the item is in these categories (from aspect)
                            "262024",  # Vintage & Antique Jewelry
                            "166734",  # Other Vintage & Antique Jewelry
                            "262011",  # Jewelry Sets
                            "262003",  # Bracelets & Charms
                            "262013",  # Necklaces & Pendants
                            }:
                            item_length = add_inches_to_sizes(extract_size_from_aspect(name, value))
                        if name in ("Material", "Upper Material"):
                            material = value
                        if name == "Brand":
                            brand = item_details.get('brand', value if name == "Brand" else '').title()
                            brand = re.sub(r"['’]S", "'s", brand)
                            logger.debug(f"Brand: {brand}")

                    ########## Now pass the item shortDescription and brand to the function

                    # Initialize first
                    size_to_process = None

                    # TODO: fall back to extracting size from shortDescription (disabled; needs refinement)

                    # Extract the title and brand from item_details
                    title = item_details.get('title', '')
                    logger.debug('title value %s', title)

                    size_to_process = extract_size_to_process(title, brand)
                    logger.debug(f"Size extracted from title and categoryId: {size_to_process}, {category_id}")



                    if size_to_process:
                        logger.debug('MAKE SURE SIZE CATEGORY ID IS LISTED SOMEWHERE IN IF STATEMENTS. OTHERWISE SIZES WONT SAVE.')

                        if isinstance(size_to_process, str):
                            logger.debug('initial size_to_process assigned to size %s', size)
                            # assign 'size' right away if a str, and if there are other size values present, size will be overwritten by further code processing
                            size = size_to_process.strip().upper()  # Ensure no extra spaces and convert to uppercase

                        # Initialize sizes to ensure they always have a value
                        numeric_size = None
                        numeric_plain_size = None
                        non_numeric_size =  None
                        standalone_size = None

                        if category_id == "262014":  # Jewelry - Rings category ID
                            if ring_size is None:
                                ring_size = size_to_process
                                logger.debug('ring size from title %s', ring_size)
                        elif category_id == "262013":  # Jewelry - Necklaces & Pendants category ID
                            if necklace_length is None:
                                necklace_length = add_inches_to_sizes(necklace_length)
                        elif category_id in {
                            "262024",  # Vintage & Antique Jewelry
                            "166734",  # Other Vintage & Antique Jewelry
                            "262011",  # Jewelry Sets
                            "262003",  # Bracelets & Charms
                            "262013",  # Necklaces & Pendants
                            }:
                            if item_length is None:
                                item_length = add_inches_to_sizes(item_length)


                        # hat in title
                        elif category_id in HAT_CATEGORY_IDS:

                            if size_to_process and isinstance(size_to_process, dict):
                                # Extract numeric_plain_size from the size_to_process dictionary
                                numeric_plain_size = size_to_process.get("numeric_plain_size")
                                logger.debug(f"Extracted numeric_plain_size for hat: {numeric_plain_size}")

                                # Check if numeric_plain_size contains a range (e.g., '57 59')
                                if numeric_plain_size and isinstance(numeric_plain_size, str):
                                    # Split the string into parts
                                    parts = numeric_plain_size.split()

                                    # Check if there are exactly two parts and both are numeric
                                    if len(parts) == 2 and all(part.isdigit() for part in parts):
                                        # Convert to integers and extract the start and end of the range
                                        start = int(parts[0])
                                        end = int(parts[1])

                                        # Generate intermediate sizes in a range of values
                                        sizes = list(range(start, end + 1))
                                        logger.debug(f"Generated sizes from range: {sizes}")

                                        # Collect all matching hat sizes
                                        matching_hat_sizes = []

                                        # Compare each size to HAT_SIZE_MAP
                                        for size in sizes:
                                            if str(size) in HAT_SIZE_MAP:
                                                matching_hat_sizes.append(HAT_SIZE_MAP[str(size)])
                                                logger.debug(f"Found matching hat size in HAT_SIZE_MAP: {HAT_SIZE_MAP[str(size)]}")

                                        # Join all matching hat sizes into a space-separated string
                                        if matching_hat_sizes:
                                            hat_size = ' '.join(matching_hat_sizes)
                                            size = None
                                            logger.debug(f"Assigned hat_size: {hat_size}")
                                        else:
                                            logger.debug("No matching hat sizes found in HAT_SIZE_MAP.")
                                    else:
                                        logger.warning("Invalid range format or non-numeric values, skipping hat size processing.")
                                else:
                                    logger.warning("numeric_plain_size is not a valid range, skipping hat size processing.")
                            else:
                                hat_size = size_to_process
                                size = None
                                logger.debug('assigned size_to_process to hat_size %s', hat_size)


                        elif category_id in {
                            "175784",  # Dresses
                            "63861",   # Dresses (women's, mod)
                            "175792",  # Suits, Sets & Suit Separates
                            "63865",   # Suits & Suit Separates (women's, mod)
                            "182050",  # Camisoles
                            "11521",   # Camisoles & Camisole Sets (women's, mod)
                            "182049",  # Bras
                            "63853",   # Bras & Bra Sets (women's, mod)
                            "182054",  # Panties
                            "63854",   # Panties (women's, mod)
                            "182056",  # Other Vintage Lingerie
                            "45279",   # Bodysuits (women's, mod) NOTE there is no direct vintage categroy equivalent
                            "182051",  # Corsets & Girdles
                            "11522",   # Corsets & Bustiers (women's, mod)
                            "182055",  # Slips & Petticoats
                            "11532",   # Slips (women's, mod)
                            "175789",  # Sleepwear & Robes
                            "63855",   # Sleepwear & Robes (women's, mod)
                            "63865",   # Suits & Suit Separates (women's, mod)
                            "175795",  # Tops
                            "53159",   # Tops (women's, mod)
                            "175791",  # Skirts
                            "63864",   # Skirts (women's, mod)
                            "175790",  # Shorts
                            "11555",   # Shorts (women's, mod)
                            "175796",  # Pants
                            "63863",   # Pants (women's, mod)
                            "175785",  # Jeans
                            "11554",   # Jeans (women's, mod)
                            "175787",  # Jumpsuits & Playsuits
                            "3009",    # Jumpsuits & Rompers (women's, mod)
                            "175786",  # Sweaters
                            "63866",   # Sweaters (women's, mod)
                            "175783",  # Coats, Jackets & Vests
                            "63862",   # Coats, Jackets & Vests (women's, mod)
                            "965",     # Other Women's Vintage Clothing
                            "74976",   # Women's shoes
                            "55793",   # Heels (women's, mod)
                            "53557",   # Boots (women's, mod)
                            "62107",   # Sandals (women's, mod)
                            "45333",   # Flats (women's, mod)
                            "95672",   # Athletic Shoes (women's, mod)
                            "111",     # Loafers (custom category ID; eBay has no 'Loafers' category)
                            "222",     # Wedges (custom category ID; eBay has no 'Wedges' category)
                            }:

                            pass

                            # Handle string-based sizes (e.g., 's', 'm', '30x31', etc.)
                            size_info = {
                                "numeric_size": None,
                                "numeric_plain_size": None,
                                "non_numeric_size": None,
                                "standalone_size": None,
                                "waist_size": None,
                                "inseam": None,
                                "hat_size": None,
                                "chest_size": None,
                                "hip_size": None,
                                "bra_size": None,
                                "bottoms_size": None,

                                "foot_length_in": None,
                                "us_shoe_size": None,
                                "shoe_size_width": None,
                                "europe_shoe_size": None,
                                "uk_shoe_size": None,
                                "france_shoe_size": None,
                                "japan_shoe_size": None,
                                "korea_china_shoe_size": None,
                            }

                            if isinstance(size_to_process, dict):
                                # Handle dictionary-based sizes (if applicable)
                                numeric_size = size_to_process.get("numeric_size")
                                numeric_plain_size = size_to_process.get("numeric_plain_size")
                                non_numeric_size = size_to_process.get("non_numeric_size")
                                standalone_size = size_to_process.get("standalone_size")
                                waist_size_to_process = size_to_process.get("waist_size")
                                inseam_from_title = size_to_process.get("inseam")
                                chest_size_to_process = size_to_process.get("chest_size")
                                hip_size_to_process = size_to_process.get("hip_size")
                                bra_size_to_process = size_to_process.get("bra_size")
                                bottoms_size_to_process = size_to_process.get("bottoms_size")

                                shoe_size_in_from_title = size_to_process.get("foot_length_in")
                                shoe_size_to_process = size_to_process.get("us_shoe_size")
                                shoe_size_width_from_title = size_to_process.get("shoe_size_width")
                                shoe_size_it_from_title = size_to_process.get("europe_shoe_size")
                                shoe_size_uk_from_title = size_to_process.get("uk_shoe_size")
                                shoe_size_fr_from_title = size_to_process.get("france_shoe_size")
                                shoe_size_jp_from_title = size_to_process.get("japan_shoe_size")
                                shoe_size_kr_from_title = size_to_process.get("korea_china_shoe_size")

                                # Populate size_info with extracted values
                                # Update size_info directly from the dictionary
                                size_info.update({
                                    "numeric_size": numeric_size,
                                    "numeric_plain_size": numeric_plain_size,
                                    "non_numeric_size": non_numeric_size,
                                    "standalone_size": standalone_size,
                                    "waist_size": waist_size_to_process,
                                    "inseam": inseam_from_title,
                                    "chest_size": chest_size_to_process,
                                    "hip_size": hip_size_to_process,
                                    "bra_size": bra_size_to_process,
                                    "bottoms_size": bottoms_size_to_process,

                                    "foot_length_in": shoe_size_in_from_title,
                                    "us_shoe_size": shoe_size_to_process,
                                    "shoe_size_width": shoe_size_width_from_title,
                                    "europe_shoe_size": shoe_size_it_from_title,
                                    "uk_shoe_size": shoe_size_uk_from_title,
                                    "france_shoe_size": shoe_size_fr_from_title,
                                    "japan_shoe_size": shoe_size_jp_from_title,
                                    "korea_china_shoe_size": shoe_size_kr_from_title,
                                })

                                if shoe_size_in_from_title:
                                    foot_length_in = shoe_size_in_from_title
                                    logger.debug(f"foot_length_in from title or description: {foot_length_in}")

                                if shoe_size_to_process:
                                    us_shoe_size = shoe_size_to_process
                                    logger.debug(f"us_shoe_size from title or description: {us_shoe_size}")

                                if shoe_size_width_from_title:
                                    shoe_size_width = shoe_size_width_from_title
                                    logger.debug(f"shoe_size_width from title save_selected_items: {shoe_size_width}")

                                if shoe_size_it_from_title:
                                    europe_shoe_size = shoe_size_it_from_title
                                    logger.debug(f"europe_shoe_size from title or description: {europe_shoe_size}")

                                if shoe_size_uk_from_title:
                                    uk_shoe_size = shoe_size_uk_from_title
                                    logger.debug(f"uk_shoe_size from title or description: {uk_shoe_size}")

                                if shoe_size_fr_from_title:
                                    france_shoe_size = shoe_size_fr_from_title
                                    logger.debug(f"france_shoe_size from title or description: {france_shoe_size}")

                                if shoe_size_jp_from_title:
                                    japan_shoe_size = shoe_size_jp_from_title
                                    logger.debug(f"japan_shoe_size from title or description: {japan_shoe_size}")

                                if shoe_size_kr_from_title:
                                    korea_china_shoe_size = shoe_size_kr_from_title
                                    logger.debug(f"korea_china_shoe_size from title or description: {korea_china_shoe_size}")

                                if hip_size_to_process:
                                    hip_size = add_inches_to_sizes(hip_size_to_process)
                                    logger.debug(f"hip_size from title or description: {hip_size}")

                                if chest_size_to_process:
                                    chest_size = add_inches_to_sizes(chest_size_to_process)
                                    logger.debug(f"chest size from title or description: {chest_size}")

                                if bra_size_to_process:
                                    bra_size = bra_size_to_process.upper()
                                    logger.debug(f"bra_size from title or description: {bra_size}")

                                if inseam_from_title:
                                    inseam = add_inches_to_sizes(inseam_from_title)
                                    logger.debug(f"inseam size from title or description: {inseam}")

                                if waist_size_to_process:
                                    waist_size = add_inches_to_sizes(waist_size_to_process)
                                    logger.debug(f"waist_size from title or description: {waist_size}")

                                if waist_size_to_process is None: # if waist_size is none, see if it is detected in numeric_size
                                    logger.debug('numeric_size detected: %s', numeric_size)
                                    if isinstance(numeric_size, str) and numeric_size.isdigit():  # Ensure numeric_size is a string and purely numeric
                                        numeric_size = int(numeric_size)  # Convert string to integer
                                        logger.debug('get size_info for numeric_size: %s', numeric_size)
                                    elif isinstance(numeric_size, int):  # If already an integer, process directly
                                            numeric_size = int(numeric_size)  # Convert string to integer
                                            logger.debug('get size_info for numeric_size: %s', numeric_size)
                                            if 20.5 <= numeric_size <= 39.5:   # General body sizes (logical waist size range)
                                                title = item_details.get('title', '').lower()
                                                # check to see if bottoms terms are present in title, meaninga plain numeric size like '36' would most likey a waist size if a word like 'pants' were in the title, otherwise don't save it to waist_size
                                                if any(term in title for term in BOTTOMS_TERMS):
                                                    waist_size = add_inches_to_sizes(numeric_size)
                                                    logger.debug('waist_size added %s', waist_size)
                                                else: # reassign numeric_size to chest_size if certain terms are in the title
                                                    if any(term in title for term in TOPS_TERMS):
                                                        chest_size = add_inches_to_sizes(numeric_size)
                                                        logger.debug('chest_size added %s', chest_size)

                                if bottoms_size_to_process:
                                    bottoms_size = bottoms_size_to_process
                                    logger.debug(f"bottoms_size from title or description: {bottoms_size}")

                                # Special handling for extracting multiple sizes from title at once
                                # Combine all non-empty size components into a single string
                                logger.debug("Starting size combination logic...")
                                size_components = [
                                    size_info.get("numeric_size", ""),
                                    size_info.get("numeric_plain_size", ""),
                                    size_info.get("non_numeric_size", ""),
                                    size_info.get("standalone_size", ""),
                                ]

                                # Process numeric_plain_size first to avoid overwriting standalone_size
                                if numeric_plain_size:
                                    logger.debug('get size_info for numeric_plain_size: %s', numeric_plain_size)
                                    size_components.append((numeric_plain_size))

                                if non_numeric_size:
                                    size_components.append(non_numeric_size)
                                    logger.debug(f"non_numeric_size size from title or description: {non_numeric_size}")

                                # Now process standalone_size and combine it with numeric_plain_size
                                if standalone_size:
                                    # Only standalone size exists
                                    size_components.append(standalone_size)
                                    logger.debug(f"Standalone size from title or description: {standalone_size}")
                                elif numeric_plain_size:
                                    if bottoms_size is None:
                                        # Only numeric plain size exists
                                        size_components.append(str(numeric_plain_size))
                                        logger.debug(f"Numeric plain size from title or description: {numeric_plain_size}")

                                # Make `size_components` lowercase + strip spaces for combining potential duplicates
                                size_components = [str(component).lower().strip() for component in size_components if component and str(component).lower() != "none"]
                                logger.debug('Size components after lowercasing: %s', size_components)

                                # Convert existing size from aspect (if it exists) to a list if it's a single string
                                if isinstance(size, str) and size.strip().lower() != 'none':
                                    # Remove or replace unwanted characters like '-', '/', etc.
                                    cleaned_size = size.replace('-', ' ').replace('/', ' ')  # Replace '-' and '/' with spaces
                                    logger.debug('cleaned size %s', cleaned_size)

                                    # Split and filter through is_valid_size
                                    split_sizes = cleaned_size.lower().split()
                                    existing_size_list = [s for s in split_sizes if is_valid_size(s)]  # Only keep valid sizes
                                    logger.debug('Size is str. existing_size_list (after validation): %s', existing_size_list)
                                else:
                                    existing_size_list = size if isinstance(size, list) else []  # Ensure it's a list or default to empty
                                    logger.debug('Size is list. existing_size_list: %s', existing_size_list)

                                # Filter numeric components of `existing_size_list` to keep only those <= 20
                                filtered_existing_size_list = [
                                    component for component in existing_size_list
                                    if not component.isdigit() or int(component) <= 20
                                ]
                                logger.debug('Filtered existing_size_list: %s', filtered_existing_size_list)

                                # Split any multi-size components (e.g., 's m') into individual sizes
                                expanded_size_components = []
                                for component in size_components:
                                    if " " in component:  # If the component contains spaces, split it
                                        expanded_size_components.extend(component.split())
                                    else:
                                        expanded_size_components.append(component)

                                # Combine filtered existing size from aspect (if it exists) + new size components
                                combined_sizes = filtered_existing_size_list + expanded_size_components
                                logger.debug('combined_sizes %s', combined_sizes)

                                # Define a mapping for cleaning specific size patterns
                                SPECIALTY_SIZE_CLEANING_MAPPING = {
                                    's/p': 'SP',
                                    'xs/p': 'SP',
                                    'l/t': 'LT',
                                    'xl/t': 'LT',
                                    'm/p': 'MP',
                                }

                                # Deduplicate by lowercasing, sorting to preserve order, then uppercasing the final output
                                unique_sizes = sorted(set(combined_sizes), key=combined_sizes.index)  # Preserve original order

                                cleaned_sizes = []

                                # Process the unique_sizes first
                                cleaned_sizes = [
                                    SPECIALTY_SIZE_CLEANING_MAPPING.get(size.lower(), size.upper())
                                    for size in unique_sizes
                                ]

                                # First clean and process the size values (applies to all item types)
                                if isinstance(bottoms_size, (int, float)):
                                    bottoms_size = str(bottoms_size)
                                elif isinstance(bottoms_size, list):
                                    bottoms_size = " ".join(map(str, bottoms_size)).strip()

                                # Only process bottoms_size if it has meaningful content
                                if bottoms_size and bottoms_size.strip():
                                    # Combine with size field if needed
                                    if size is not None:
                                        bottoms_size += " " + str(size)
                                        logger.debug('Combined bottoms_size: %s', bottoms_size)

                                    # Deduplicate and clean bottoms sizes
                                    unique_sorted_sizes = sorted(set(bottoms_size.split()), key=lambda x: bottoms_size.index(x))

                                    # Only overwrite cleaned_sizes if bottoms processing produces meaningful results
                                    if unique_sorted_sizes:
                                        bottoms_cleaned_sizes = [
                                            SPECIALTY_SIZE_CLEANING_MAPPING.get(size.lower(), size.upper())
                                            for size in unique_sorted_sizes
                                        ]
                                        # Only overwrite if bottoms processing gives us something meaningful
                                        if bottoms_cleaned_sizes and any(size for size in bottoms_cleaned_sizes):
                                            cleaned_sizes = bottoms_cleaned_sizes
                                            logger.debug("Used bottoms_size processing")

                                logger.debug('Cleaned sizes: %s', cleaned_sizes)

                                # Now handle the type-specific assignments INDEPENDENTLY
                                if 'versace jeans' in title.lower() or 'armani jeans' in title.lower(): # Check for brand name exceptions to avoid accidentally sorting none 'jean' items as a 'jean' bottoms size e.g. the brand name in title doesnt mean it's a 'jeans' item, it could be a skirt
                                    is_bottoms = False
                                else:
                                    is_bottoms = any(re.search(r'\b' + re.escape(term) + r'\b', title) for term in BOTTOMS_TERMS) # Use word boundaries to match bottoms terms more precisely
                                is_shoe = category_id in CATEGORY_MAPPINGS.get("Shoes", [])
                                is_hat = hat_size is not None

                                if is_bottoms:
                                    bottoms_size = " ".join(cleaned_sizes) if cleaned_sizes else None
                                    size = None  # Clear regular size field
                                    logger.debug(f'Assigned to bottoms_size: {bottoms_size}')

                                if is_shoe:
                                    if us_shoe_size is None and cleaned_sizes:
                                        us_shoe_size = " ".join(cleaned_sizes)
                                        logger.debug(f'Assigned to us_shoe_size: {us_shoe_size}')
                                    size = None  # Always clear regular size for shoes

                                if is_hat:
                                    size = None  # Clear regular size for hats
                                    logger.debug('Hat detected - size cleared')

                                # Default size assignment (only if not a special type)
                                if not any([is_bottoms, is_shoe, is_hat]) and cleaned_sizes:
                                    # Sort the sizes before joining
                                    sorted_sizes = sorted(cleaned_sizes, key=get_size_order)
                                    size = " ".join(sorted_sizes)
                                    logger.debug(f'Assigned to size: {size} (sorted from: {cleaned_sizes})')


                        elif category_id in {
                            "163601",  # Vintage Belts
                            "163600",  # Belt Buckle
                            "52557",   # Belts (modern)
                            }:
                            logger.debug('belt detected')
                            # For belts, numeric size goes to waist_size, letter size goes to size
                            if isinstance(size_to_process, dict):
                                # Handle numeric size (for waist measurement)
                                numeric_size = size_to_process.get("numeric_plain_size")
                                if numeric_size:
                                    waist_size = add_inches_to_sizes(numeric_size)

                                waist_size = size_to_process.get("waist_size")
                                if waist_size:
                                    logger.debug('waist detected')
                                    waist_size = add_inches_to_sizes(waist_size)

                                # Handle letter size (S/M/L etc)
                                standalone_size = size_to_process.get("standalone_size")
                                if standalone_size:
                                    size = standalone_size.upper()
                                else:
                                    size = None  # Clear size if no letter size exists


                    else:
                        if isinstance(size_to_process, dict):
                            logger.debug('final size_to_process %s', size_to_process)
                            # For unhandled categories, just combine all available sizes
                            size_parts = []
                            if size_to_process.get("numeric_plain_size"):
                                size_parts.append(str(size_to_process["numeric_plain_size"]))
                            if size_to_process.get("standalone_size"):
                                size_parts.append(size_to_process["standalone_size"].upper())
                            size = " ".join(size_parts) if size_parts else None
                        elif isinstance(size_to_process, str):
                            size = size_to_process.upper()
                        else:
                            # Keep existing size unchanged for unhandled cases
                            logger.debug(f'keeping existing size: {size}')

                    if category_id == "74976":  # Women's shoes
                        # Reassign category_id based on keywords in the title
                        title = item_details.get('title', '').lower()
                        # Remove punctuation from the title so it doesnt interfere with shoe keyword titlematching
                        title = re.sub(r'[^\w\s]', '', title)  # Remove all non-alphanumeric characters
                        logger.debug('cleaned title: %s', title)

                        if any(keyword in title for keyword in ['ballerina', 'ballerinas', 'flats']):
                            category_id = "45333"  # Flats (women's, mod)
                        elif any(keyword in title for keyword in ['sneaker', 'sneakers', 'tennis shoe', 'tennis shoes', 'athletic shoe', 'athletic shoes', 'running shoe', 'running shoes']):
                            category_id = "95672"  # Athletic Shoes (women's, mod)
                        elif any(keyword in title for keyword in ['loafer', 'loafers', 'moccasin', 'moccasins', 'oxford', 'oxfords']):
                            category_id = "111"  # Loafers (custom category)
                        elif any(keyword in title for keyword in ['wedges', 'wedge']):
                            category_id = "222"  # Wedges (custom category)
                        elif any(keyword in title for keyword in ['heel', 'heels', 'peep toe', 'platform', 'platforms', 'pump', 'pumps', 'stiletto', 'stilettos']):
                            category_id = "55793"  # Heels (women's, mod)
                        elif any(keyword in title for keyword in ['boot', 'boots', 'booties']):
                            category_id = "53557"  # Boots (women's, mod)
                        elif any(keyword in title for keyword in ['sandal', 'sandals', 'espadrille', 'espadrilles']):
                            category_id = "62107"  # Sandals (women's, mod)
                        else:
                            # Default to the original category_id if no keywords match
                            logger.debug('No matching keywords found in title. Keeping original category_id: %s', category_id)

                    # Normalize the size to uppercase before saving
                    if size:
                        size = str(size).upper()  # Convert size to string and then to uppercase

                    if women_size:
                        women_size = women_size.upper()

                    if bottoms_size:
                        # Make sure bottoms_size is a string before calling upper()
                        if isinstance(bottoms_size, list):
                            bottoms_size = ' '.join(bottoms_size)  # Join the list into a single string if it's a list

                        elif isinstance(bottoms_size, int):
                            bottoms_size = str(bottoms_size).upper().replace("/", " ")  # Convert to str to process numeric AND non-numeric sizes like 'M'

                    if ebay_env == 'sandbox':
                        webp_image_url = 'webp_images/ebay-fallback-image.webp'
                    else:
                        image_data = item_details.get('image')
                        if image_data and image_data.get('imageUrl'):
                            webp_image_url = convert_image_to_webp(image_data['imageUrl'], item_details.get('title', '').lower())

                            # Check if gallery_url already exists
                            if CoreEbayitem.objects.filter(gallery_url=webp_image_url).exists():
                                messages.warning(request, f"Item '{item_details['title']}' already exists and was skipped.")
                                logger.warning(f"Item with gallery_url {webp_image_url} already exists, skipping...")
                                continue

                        else:
                            logger.warning(f"Warning: 'image' or 'imageUrl' not found for item_id {item_details.get('itemId')}")
                            webp_image_url = None

                    item_details = get_item_details(item_id)
                    # Get the userId from item_details
                    user_id = item_details.get('userId', 'Unknown userId')

                    shoe_size_conversion = None

                    # Check if the item's category is within the defined shoe categories
                    if str(category_id) in SHOE_CATEGORY_IDS:  # Ensure item_category_id is a string for comparison
                        # Create a ShoeSizeConversion instance
                        shoe_size_conversion = ShoeSizeConversion.objects.create(
                            foot_length_in=foot_length_in if foot_length_in else None,
                            us_shoe_size=us_shoe_size if us_shoe_size else None,
                            europe_shoe_size=europe_shoe_size if europe_shoe_size else None,
                            uk_shoe_size=uk_shoe_size if uk_shoe_size else None,
                            france_shoe_size=france_shoe_size if france_shoe_size else None,
                            japan_shoe_size=japan_shoe_size if japan_shoe_size else None,
                            korea_china_shoe_size=korea_china_shoe_size if korea_china_shoe_size else None,
                        )



                    # Create the item only if both item_id and gallery_url are unique
                    new_item = CoreEbayitem.objects.create(
                        title=item_details['title'], # sandbox: title[0]
                        price=item_details['price']['value'], # sandbox: price_list[0]
                        item_id=item_id,
                        gallery_url=webp_image_url,
                        item_web_url=item_details['itemAffiliateWebUrl'], # sandbox: itemAffiliateWebUrl[0]
                        availability=availability_status,
                        itemCreationDate=itemCreationDate,
                        itemEndDate=itemEndDate,
                        color=normalized_single_color,
                        size=size,
                        bottoms_size=bottoms_size,
                        brand=brand,
                        women_size=women_size,
                        us_shoe_size=us_shoe_size,
                        shoe_size_width=shoe_size_width,
                        shoe_size_conversion=shoe_size_conversion, # Link the ShoeSizeConversion instance
                        hat_size=hat_size,
                        chest_size=chest_size,
                        bra_size=bra_size,
                        waist_size=waist_size,
                        inseam=inseam,
                        hip_size=hip_size,
                        waist_to_hem=waist_to_hem,
                        shoulder_to_shoulder=shoulder_to_shoulder,
                        shoulder_to_hem=shoulder_to_hem,
                        ring_size=ring_size,
                        necklace_length=necklace_length,
                        item_length=item_length,
                        material=material,
                        categoryId=category_id,
                        categoryIdPath=item_details.get('categoryIdPath', ''),
                        user_id=user_id,
                        username=seller_username,
                    )
                    new_items.append(new_item.id)

                elif CoreEbayitem.objects.filter(item_id=item_id).exists():
                    logger.debug('ITEM ALREADY EXISTS IN DATABASE!!!! SAVE ITEMS DETAILS WILL NOT BE EXTRACTED')
                timestamp.save()

            return JsonResponse({'status': 'success', 'saved_item_ids': new_items, 'timestamp': timestamp.timestamp}, status=201)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.exception("Unhandled exception")
            return JsonResponse({'error': 'Server error: ' + str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=400)


@admin_required
def display_search_results(request):  # search_results.html
    # Fetch items from database
    db_items = CoreEbayitem.objects.order_by('-id')
    db_items_sold = CoreEbayitemSold.objects.defer('created_at').extra(
        select={'date_sold': 'STR_TO_DATE(itemEndDate, "%%Y-%%m-%%d %%H:%%i:%%s")'}
    ).order_by('-date_sold')

    # Get search parameters
    query = request.GET.get('query', '')
    username = request.GET.get('username', '')

    # Get saved usernames for dropdown
    username_file = os.path.join(settings.BASE_DIR, 'saved_usernames.txt')
    saved_usernames = []

    try:
        if os.path.exists(username_file):
            with open(username_file, 'r') as f:
                saved_usernames = [line.strip() for line in f.readlines() if line.strip()]
        else:
            # Create file with initial username
            with open(username_file, 'w') as f:
                f.write('bulletproofdaisyvtg\n')
            saved_usernames = ['bulletproofdaisyvtg']
    except Exception as e:
        logger.error(f"Username file error: {e}")
        saved_usernames = ['bulletproofdaisyvtg']

    # OPTIMIZED: Cache categories for 1 hour
    cached_categories = cache.get('ebay_categories')
    if cached_categories:
        _, all_category_names, _, _, _, _, _ = cached_categories
    else:
        category_data = create_categories()
        all_category_names = category_data[1]  # Extract category names

        # Cache for 1 hour (3600 seconds)
        cache.set('ebay_categories', category_data, 3600)
        _, all_category_names, _, _, _, _, _ = category_data

    # Make API call to eBay
    limit = 200 # IMPORTANT: 200 is the eBay max per request; anything higher breaks search
    categoryId = request.GET.get('category_id', '')
    categoryIdPath = categoryId

    # Check if search is needed and make API call
    has_search_params = bool(query.strip() or username.strip() or categoryId.strip())

    results = []
    username_error = None
    username_valid = False

    if has_search_params:
        results = search_ebay_items(query, username, categoryId, categoryIdPath, limit, settings.EBAY_CREDENTIALS, settings.EBAY_ENV)

        # If username was provided, validate that results actually come from that seller
        if username and username.strip():
            username_to_check = username.strip().lower()

            if results:
                # Check if any results actually match the requested username
                matching_results = []
                for item in results:
                    seller_info = item.get('seller', {})
                    seller_username = seller_info.get('username', '').lower()

                    if seller_username == username_to_check:
                        matching_results.append(item)
                        username_valid = True

                if matching_results:
                    # Only show results that match the username
                    results = matching_results
                    logger.debug(f"Found {len(results)} items from username '{username.strip()}'")
                else:
                    # Results exist but none match the username - username doesn't exist
                    results = []
                    username_error = f"eBay username '{username.strip()}' does not exist. Please check the spelling."
                    logger.warning(f"Username '{username.strip()}' not found in search results")
            else:
                # No results at all
                if not query.strip() and not categoryId.strip():
                    # Username-only search with no results means username doesn't exist
                    username_error = f"eBay username '{username.strip()}' does not exist. Please check the spelling."
                    logger.error(f"Username-only search failed for '{username.strip()}'")
                # For combined searches with no results, don't show error - let existing message handle it

    # Only save username if it's valid (found actual results from that seller)
    # EDIT/REMOVE saved usernames at ClothingApp/saved_usernames.txt
    if username and username.strip() and username_valid:
        username_to_save = username.strip()
        if username_to_save.lower() not in [u.lower() for u in saved_usernames]:
            try:
                with open(username_file, 'a') as f:
                    f.write(f'{username_to_save}\n')
                saved_usernames.append(username_to_save)
                logger.debug(f"Saved valid username: {username_to_save}")
            except Exception as e:
                logger.error(f"Error saving username: {e}")
    elif username and username.strip() and not username_valid:
        logger.warning(f"Not saving invalid username: {username.strip()}")


    # OPTIMIZED: Skip expensive item details call for faster initial load
    item_details = None

    # Check for quick save success message
    quick_save_success = request.GET.get('quick_save_success')
    if quick_save_success:
        messages.success(request, f'Item {quick_save_success} saved successfully!')

    # Enhance image resolution for search results
    if results:
        for i, item in enumerate(results):
            image_data = item.get('image', {})
            if image_data and image_data.get('imageUrl'):
                original_url = image_data['imageUrl']

                # Try different eBay image size patterns
                enhanced_url = original_url
                if 's-l225.jpg' in original_url:
                    enhanced_url = original_url.replace('s-l225.jpg', 's-l400.jpg')
                elif 's-l' in original_url and '.jpg' in original_url:
                    enhanced_url = re.sub(r's-l\d+\.jpg', 's-l400.jpg', original_url)

                if enhanced_url != original_url:
                    # Update the imageUrl in the search results
                    results[i]['image']['imageUrl'] = enhanced_url

    all_valid_colors = VALID_COLORS  # If VALID_COLORS is a dict
    # Sort alphabetically for better UX
    all_valid_colors = sorted(all_valid_colors)


    def add_sold_day(item, timezone='America/New_York'):
        try:
            # Database stores UTC time - must convert to local timezone to match eBay's display
            # Example: Mon 6:50 PM EST = Tue 1:50 AM UTC (appears as wrong day without conversion)
            dt = datetime.strptime(item.itemEndDate, '%Y-%m-%d %H:%M:%S')
            dt_utc = pytz.UTC.localize(dt)

            local_tz = pytz.timezone(timezone)
            dt_local = dt_utc.astimezone(local_tz)

            item.sold_day = dt_local.strftime('%A')
        except:
            item.sold_day = ''

    for item in db_items_sold:
        add_sold_day(item, 'America/New_York')

    for item in db_items:
        add_sold_day(item, 'America/New_York')

    context = {
        'distinct_colors': all_valid_colors,
        'search_results': results,
        'query': query,
        'username': username,
        'username_error': username_error,  # Only username errors
        'saved_usernames': saved_usernames,
        'item_details': item_details,
        'db_items': db_items,
        'db_items_sold': db_items_sold,
        'categoryIdPath': categoryIdPath,
        'category_names': all_category_names,
        'in_stock_count': db_items.filter(availability='IN_STOCK').count(),
        'ended_count': db_items.filter(availability='ENDED').count(),
        'sold_main_count': db_items.filter(availability='OUT_OF_STOCK').count(),
        'sold_archive_count': db_items_sold.count(),

    }

    return render(request, 'core/search_results.html', context)

@admin_required
def update_category(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            item_id = data.get('itemId')
            category_id = data.get('categoryId')
            if not item_id or not category_id:
                return JsonResponse({'error': 'Missing item ID or category ID'}, status=400)
            color = data.get('color')
            featured = data.get('featured', False)

            # Update the category ID of the CoreEbayItem instance
            item = CoreEbayitem.objects.get(item_id=item_id)
            item.categoryId = category_id

            # Update color if provided
            if color:  # Only update if color is not empty
                item.color = color

            item.featured = featured

            item.save()

            return JsonResponse({'status': 'success', 'message': 'Category updated successfully'}, status=200)
        except CoreEbayitem.DoesNotExist:
            return JsonResponse({'error': 'Item not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': 'Server error: ' + str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=400)
