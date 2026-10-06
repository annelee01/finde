import os, json, re
from django.conf import settings

from .models import CoreEbayitem, CoreEbayitemSold, Timestamp, ShoeSizeConversion
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .decorators import admin_required
from django.contrib.auth.models import User
from django.core.files.storage import default_storage
from .fashion_taxonomy import fashion_taxonomy
import logging

logger = logging.getLogger(__name__)

def calculate_time_since_update():
    try:
        # Fetch the latest timestamp
        latest_timestamp = Timestamp.objects.latest('timestamp').timestamp

        # Calculate the time difference
        time_difference = timezone.now() - latest_timestamp

        # Convert time difference to minutes
        minutes_since_update = int(time_difference.total_seconds() / 60)

        # Determine the appropriate time format based on the time elapsed
        if minutes_since_update < 60:
            formatted_time_since_update = f"Updated {minutes_since_update} minute{'s' if minutes_since_update != 1 else ''} ago"
        elif minutes_since_update < 1440:  # Less than 24 hours
            hours_since_update = minutes_since_update // 60
            formatted_time_since_update = f"Updated {hours_since_update} hour{'s' if hours_since_update != 1 else ''} ago"
        else:
            days_since_update = minutes_since_update // 1440
            formatted_time_since_update = f"Updated {days_since_update} day{'s' if days_since_update != 1 else ''} ago"

        return formatted_time_since_update

    except ObjectDoesNotExist:
        # Handle the case where there are no timestamps yet
        pass

# Define color mappings at module level (single source of truth)
COLOR_MAPPING = {
    "tan": "beige",
    "ivory": "cream",
    "creme": "cream",
    "transparent": "clear",
    "coral": "orange",
    "mango": "orange",
    "olive": "green",
    "lime": "green",
    "violet": "purple",
    "lilac": "purple",
    "indigo": "purple",
    "aqua": "turquoise",
    "seafoam": "turquoise",
    "mint": "turquoise",
    "teal": "turquoise",
    "grey": "gray",
    "multi": "multicolor",
    "multi-color": "multicolor",
    "multi color": "multicolor",
    # Additional color variations
    "maroon": "burgundy",
    "wine": "burgundy",
    "crimson": "red",
    "scarlet": "red",
    "cherry": "red",
    "rose": "pink",
    "blush": "pink",
    "salmon": "pink",
    "magenta": "pink",
    "fuchsia": "pink",
    "emerald": "green",
    "forest": "green",
    "sage": "green",
    "chartreuse": "green",
    "kelly": "green",
    "royal": "blue",
    "navy": "navy",  # Maps to itself (already in VALID_COLORS)
    "cobalt": "blue",
    "sky": "blue",
    "powder": "blue",
    "periwinkle": "blue",
    "lavender": "purple",
    "plum": "purple",
    "amethyst": "purple",
    "mauve": "purple",
    "mustard": "yellow",
    "lemon": "yellow",
    "canary": "yellow",
    "amber": "yellow",
    "gold": "gold",  # Maps to itself
    "bronze": "bronze", # Maps to itself
    "brass": "bronze",
    "brassy": "bronze",
    "chocolate": "brown",
    "coffee": "brown",
    "mocha": "brown",
    "camel": "brown",
    "rust": "brown",
    "copper": "brown",
    "mahogany": "brown",
    "chestnut": "brown",
    "pewter": "gray",
    "charcoal": "gray",
    "slate": "gray",
    "steel": "gray",
    "ash": "gray",
    "silver": "silver",  # Maps to itself
    "platinum": "silver",
    "metallic": "silver",
    "pearl": "white",
    "off-white": "white",
    "off white": "white",
    "eggshell": "white",
    "bone": "white",
    "vanilla": "cream",
    "butter": "cream",
    "champagne": "cream",
    "nude": "beige",
    "khaki": "beige",
    "sand": "beige",
    "taupe": "beige",
    "stone": "beige",
    "oatmeal": "beige",
    "ecru": "beige",
    "jet": "black",
    "ebony": "black",
    "onyx": "black",
    "midnight": "black",
    "coal": "black",
}

VALID_COLORS = {
    "white", "cream", "beige", "brown", "bronze", "burgundy", "red",
    "orange", "yellow", "green", "turquoise", "blue", "navy",
    "purple", "pink", "black", "gray", "silver", "gold", "clear", "multicolor"
}

# Define which colors should have precise search (no expansion to normalized colors) e.g. 'lime' should not match 'green'
PRECISE_COLOR_TERMS = {
    "lime", "olive", "violet", "lilac", "indigo", "aqua", "seafoam", 
    "mint", "teal", "coral", "mango", "tan", "ivory", "creme", "maroon", "wine",
    "crimson", "scarlet", "cherry", "rose", "blush", "salmon", "magenta",
    "fuchsia", "emerald", "forest", "sage", "chartreuse", "kelly", "royal",
    "cobalt", "sky", "powder", "periwinkle", "lavender", "plum", "amethyst",
    "mauve", "mustard", "lemon", "canary", "amber", "bronze", "chocolate",
    "coffee", "mocha", "camel", "rust", "copper", "mahogany", "chestnut",
    "pewter", "charcoal", "slate", "steel", "ash", "platinum", "metallic",
    "pearl", "off-white", "off white", "eggshell", "bone", "vanilla", "butter", "champagne",
    "nude", "khaki", "sand", "taupe", "stone", "oatmeal", "ecru", "jet",
    "ebony", "onyx", "midnight", "coal"
}

def normalize_single_color(color):
    """Normalize a single color to its canonical form for display purposes"""
    if not color:
        return None
    
    # Clean the color string
    color_clean = color.strip().lower()
    
    # First check if the full color string (potentially multi-word) is in our mapping
    mapped_color = COLOR_MAPPING.get(color_clean)
    if mapped_color and mapped_color in VALID_COLORS:
        return mapped_color
    
    # If the full string is already a valid color, return it
    if color_clean in VALID_COLORS:
        return color_clean
    
    # If it's a multi-word color that wasn't found, try variations
    # Handle common multi-word patterns
    if ' ' in color_clean:
        # For patterns like "off white", "multi color", etc.
        if color_clean in COLOR_MAPPING:
            mapped_color = COLOR_MAPPING[color_clean]
            if mapped_color in VALID_COLORS:
                return mapped_color
    
    # Last resort: try just the first word (original behavior)
    first_word = color_clean.split()[0]
    mapped_color = COLOR_MAPPING.get(first_word, first_word)
    if mapped_color in VALID_COLORS:
        return mapped_color
    
    return None

def get_color_variants_for_search(term):
    """Get color variants for search - handles precise vs normalized color matching"""
    variants = [term]  # Always include original term
    term_lower = term.lower()
    
    # Check if this is a precise color term that should NOT be expanded
    if term_lower in PRECISE_COLOR_TERMS:
        logger.debug(f"'{term}' is a precise color term - searching title only, no color field expansion")
        
        # For precise color terms, DON'T add any variants
        # This will make the search only match the exact term in title/brand/material
        # and NOT search the normalized color field
        
        # Only exception: bidirectional gray/grey mapping
        if term_lower == "gray":
            variants.append("grey")
        elif term_lower == "grey":
            variants.append("gray")
        
        return list(set(variants))
            
    else:
        # For non-precise terms (like "green", "blue", "red"), expand normally
        normalized_color = normalize_single_color(term)
        if normalized_color:
            variants.append(normalized_color)
            
            # Add all the specific variants that map to this normalized color
            for original, mapped in COLOR_MAPPING.items():
                if mapped == normalized_color and original not in variants:
                    variants.append(original)
                elif mapped == term_lower and original not in variants:
                    variants.append(original)
    
    # Remove duplicates and return
    final_variants = list(set(variants))
    return final_variants


def get_all_color_variants_for_normalized(normalized_color):
    """Helper function: get all original colors that map to a normalized color"""
    variants = [normalized_color]
    for original, mapped in COLOR_MAPPING.items():
        if mapped == normalized_color:
            variants.append(original)
    return variants

def normalize_colors():
    distinct_colors = CoreEbayitem.objects.filter(
        availability='IN_STOCK'
    ).exclude(
        color__icontains='unknown'
    ).exclude(
        color__iexact='none'
    ).values_list('color', flat=True).distinct()

    normalized_colors = {
        normalize_single_color(color)
        for color in distinct_colors
        if normalize_single_color(color) is not None
    }

    # display order of colors
    custom_color_order = [
        'white', 'cream', 'beige', 'brown', 'burgundy', 'red',
        'orange', 'yellow', 'green', 'turquoise', 'blue', 'navy',
        'purple', 'pink', 'gray', 'black', 'silver', 'gold', 'bronze', 'clear', 'multicolor'
    ]

    sorted_colors = sorted(
        normalized_colors,
        key=lambda x: custom_color_order.index(x) if x in custom_color_order else len(custom_color_order)
    )

    return sorted_colors





def extract_color_from_title(title):
    """Extract and normalize color from title text"""
    if not title:
        return None
    
    # Convert title to lowercase for matching
    title_lower = title.lower()
    
    # Create a comprehensive list of all possible color terms to search for
    all_color_terms = set()
    
    # Add all color mapping keys
    all_color_terms.update(COLOR_MAPPING.keys())
    
    # Add all valid colors  
    all_color_terms.update(VALID_COLORS)
    
    # Sort by length (longest first) to match more specific colors first
    sorted_color_terms = sorted(all_color_terms, key=len, reverse=True)
    
    # Look for color terms in the title
    for color_term in sorted_color_terms:
        # Use word boundaries to avoid partial matches
        pattern = r'\b' + re.escape(color_term) + r'\b'
        if re.search(pattern, title_lower):
            # Found a color term, now normalize it
            normalized = normalize_single_color(color_term)
            if normalized:
                return normalized
            # If it doesn't normalize but is in valid colors, return as-is
            elif color_term in VALID_COLORS:
                return color_term
    
    return None

def get_item_color(item_details):
    """Get color from item details, with fallback to title extraction"""
    # First try to get color from the color field
    color = item_details.get('color', '').strip()
    
    if color and color.lower() not in ['unknown', 'none', '']:
        # Clean the color field
        color = re.sub(r'[^\w\s]', ' ', color)
        # Normalize it
        normalized = normalize_single_color(color)
        return normalized if normalized else color
    
    # If no color field or it's empty/unknown, try to extract from title
    title = item_details.get('title', '')
    extracted_color = extract_color_from_title(title)
    
    return extracted_color if extracted_color else 'Unknown'

# Define a dictionary mapping category IDs to top_level_category
CATEGORY_MAPPINGS = {
    "Bags & Purses": [
        "74962",   # Bags, Handbags & Cases
        "169291",  # Women's Bags & Handbags (women's mod)
        "175769",  # Wallets & Coin Purses
        "45258",   # Wallets (women's, mod)        
    ],
    "Accessories": [
        "74969",   # Hat (women's)
        "45230",   # Hats (women's mod)
        "163619",  # Hats (men's vtg)
        "48559",   # Sunglasses
        "179247",  # Sunglasses & Sunglasses Accessories (women's mod)
        "45246",   # Women's Sunglasses
        "175805",  # Eyeglasses
        "175819",  # Hair Accessories
        "45220",   # Hair Accessories (women's, mod)
        "262010",  # Hair & Head Jewelry
        "175807",  # Scarves & Wraps
        "45238",   # Scarves & Wraps (women's mod)
        "163601",  # Belts
        "163600",  # Belt buckles
        "3003",    # Belts (women's mod)
        "957",     # Other Vintage Accessories
    ],
    "Jewelry": [
        # TODO: List modern equivalent category IDs and separate costume vs. fine jewelry
        "262024",  # Vintage & Antique Jewelry
        "262011",  # Jewelry Sets
        "262014",  # Rings
        "261994",  # Rings (women's, mod)
        "262008",  # Vintage & Antique Earrings
        "262004",  # Brooches & Pins
        "262003",  # Bracelets & Charms
        "261988",  # Bracelets & Charms (women's mod,fine)
        "262013",  # Necklaces & Pendants
        "261993",  # Necklaces & Pendants (women's mod, fine)
        "166734",  # Other Vintage & Antique Jewelry
    ],
    "Shoes": [
        "163627",  # Shoe Accessories
        "74976",   # Women's shoes
        "55793",   # Heels (women's, mod)
        "53557",   # Boots (women's, mod)
        "62107",   # Sandals (women's, mod)
        "45333",   # Flats (women's, mod)
        "95672",   # Athletic Shoes (women's, mod)
        "111",     # Loafers (custom category ID; eBay has no 'Loafers' category)
        "222",     # Wedges (custom category ID; eBay has no 'Wedges' category)

    ],
    "Clothing": [
        "175784",  # Dresses
        "63861",   # Dresses (women's, mod)
        "175792",  # Suits, Sets & Suit Separates
        "63865",   # Suits & Suit Separates (women's, mod)
        "175795",  # Tops
        "53159",   # Tops (women's, mod)
        "175791",  # Skirts
        "63864",   # Skirts (women's, mod)
        "175790",  # Shorts
        "11555",   # Shorts (women's, mod)
        "260011",  # Outfits & Sets
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
    ],
    "Loungewear & Lingerie": [
        "182050",  # Camisoles 
        "11521",   # Camisoles & Camisole Sets (women's, mod)
        "182049",  # Bras
        "63853",   # Bras & Bra Sets (women's, mod)
        "182054",  # Panties
        "63854",   # Panties (women's, mod)
        "45279",   # Bodysuits (women's, mod) NOTE there is no direct vintage categroy equivalent
        "182051",  # Corsets & Girdles
        "11522",   # Corsets & Bustiers (women's, mod)
        "182055",  # Slips & Petticoats
        "11532",   # Slips (women's, mod)
        "175789",  # Sleepwear & Robes
        "63855",   # Sleepwear & Robes (women's, mod)
        "182056",  # Other Vintage Lingerie
    ],
}

# This maps search keywords to relevant category IDs

KEYWORD_CATEGORY_MAPPINGS = {
    # Bags & Purses keywords
    'wallet': ["175769", "45258"],  # Wallets & Coin Purses, Wallets (women's, mod)
    'wallets': ["175769", "45258"],
    'purse': ["74962", "169291"],  # Bags, Women's Bags, Wallets & Coin Purses
    'purses': ["74962", "169291"],
    'bag': ["74962", "169291"],  # Bags, Women's Bags & Handbags
    'bags': ["74962", "169291"],
    'handbag': ["74962", "169291"],
    'handbags': ["74962", "169291"],
    
    # Shoes keywords
    'shoe': ["74976", "55793", "53557", "62107", "45333", "95672", "111", "222"],
    'shoes': ["74976", "55793", "53557", "62107", "45333", "95672", "111", "222"],
    'heel': ["55793"],  # Heels
    'heels': ["55793"],
    'boot': ["53557"],  # Boots
    'boots': ["53557"],
    'sandal': ["62107"],  # Sandals
    'sandals': ["62107"],
    'flats': ["45333"],  # Flats
    'sneaker': ["95672"],  # Athletic Shoes
    'sneakers': ["95672"],
    'loafer': ["111"],  # Loafers - Custom category
    'loafers': ["111"],
    'wedge': ["222"],  # Custom category
    'wedges': ["222"],
    
    # Jewelry keywords
    'jewelry': ["262024", "262011", "262014", "261994", "262008", "262003", "261988", "262013", "261993", "166734"],
    'ring': ["262014", "261994"],
    'rings': ["262014", "261994"],
    'earring': ["262008"],
    'earrings': ["262008"],
    'bracelet': ["262003", "261988"],
    'bracelets': ["262003", "261988"],
    'necklace': ["262013", "261993"],
    'necklaces': ["262013", "261993"],
    'pendant': ["262013", "261993"],
    'pendants': ["262013", "261993"],
    
    # Clothing keywords
    'dress': ["175784", "63861"],
    'dresses': ["175784", "63861"],
    'top': ["175795", "53159"],
    'tops': ["175795", "53159"],
    'shirt': ["175795", "53159"],  # Assuming shirts are in tops
    'shirts': ["175795", "53159"],
    'skirt': ["175791", "63864"],
    'skirts': ["175791", "63864"],
    'pants': ["175796", "63863"],
    'pant': ["175796", "63863"],
    'jeans': ["175785", "11554"],
    'jean': ["175785", "11554"],
    'shorts': ["175790", "11555"],
    'short': ["175790", "11555"],
    'jumpsuit': ["175787", "3009"],
    'jumpsuits': ["175787", "3009"],
    'playsuit': ["175787", "3009"],
    'playsuits': ["175787", "3009"],
    'romper': ["175787", "3009"],
    'rompers': ["175787", "3009"],
    'sweater': ["175786", "63866"],
    'sweaters': ["175786", "63866"],
    'blazer': ["175783", "63862", "175783", "63862"],
    'blazers': ["175783", "63862", "175783", "63862"],
    'coat': ["175783", "63862"],
    'coats': ["175783", "63862"],
    'jacket': ["175783", "63862"],
    'jackets': ["175783", "63862"],
    'vest': ["175783", "63862"],
    'vests': ["175783", "63862"],
    
    # Accessories keywords
    'hat': ["74969", "45230", "163619"],
    'hats': ["74969", "45230", "163619"],
    'sunglasses': ["48559", "179247"],
    'glasses': ["175805"],  # Eyeglasses
    'eyeglasses': ["175805"],
    'scarf': ["175807", "45238"],
    'scarves': ["175807", "45238"],
    'wrap': ["175807", "45238"],
    'wraps': ["175807", "45238"],
    'belt': ["163601", "3003"],
    'belts': ["163601", "3003"],
    
    # Lingerie keywords
    'bra': ["182049", "63853"],
    'bras': ["182049", "63853"],
    'panties': ["182054", "63854"],
    'underwear': ["182054", "63854"],
    'lingerie': ["182050", "11521", "182049", "63853", "182054", "63854", "45279", "182051", "11522", "182055", "11532", "175789", "63855", "182056"],
    'camisole': ["182050", "11521"],
    'camisoles': ["182050", "11521"],
    'bodysuit': ["45279"],
    'bodysuits': ["45279"],
    'corset': ["182051", "11522"],
    'corsets': ["182051", "11522"],
    'bustier': ["182051", "11522"],
    'bustiers': ["182051", "11522"],
    'slip': ["182055", "11532"],
    'slips': ["182055", "11532"],
    'petticoat': ["182055"],
    'petticoats': ["182055"],
    'sleepwear': ["175789", "63855"],
    'pajama': ["175789", "63855"],
    'pajamas': ["175789", "63855"],
    'robe': ["175789", "63855"],
    'robes': ["175789", "63855"],
}


# My custom semantic fashion taxonomy in fashion_taxonomy.py
def categorize_detected_item(detected_category):
    """Categorize a detected fashion item."""
    return fashion_taxonomy.categorize_item(detected_category)

def get_ebay_category(semantic_path, attributes=None):
    """Get eBay category for a semantic path."""
    return fashion_taxonomy.get_platform_category(semantic_path, 'ebay')

def get_top_level_category(semantic_path):
    """Get display category from semantic path."""
    return fashion_taxonomy.get_top_level_category(semantic_path)

def get_category_display_name(semantic_path):
    """Convert semantic path to human-readable display name."""
    if not semantic_path:
        return ''
    
    # Handle special cases
    if semantic_path.startswith('accessories.jewelry'):
        parts = semantic_path.split('.')
        if len(parts) >= 3:
            # accessories.jewelry.necklaces -> Jewelry > Necklaces
            return f"Jewelry > {format_category_name(parts[2])}"
    
    # Standard path formatting
    parts = semantic_path.split('.')
    formatted_parts = []
    
    for part in parts:
        formatted_parts.append(format_category_name(part))
    
    return ' > '.join(formatted_parts)

def format_category_name(category_name):
    """Convert snake_case or camelCase to readable format."""
    return category_name.replace('_', ' ').replace('-', ' ').title()

def validate_category_path(semantic_path):
    """Validate that a semantic path exists in the taxonomy."""
    if not semantic_path:
        return False
    
    try:
        # This is a simplified validation - you might want to make it more robust
        parts = semantic_path.split('.')
        if len(parts) >= 1:
            # At minimum, check if the root category exists
            from .fashion_taxonomy import FASHION_TAXONOMY
            return parts[0] in FASHION_TAXONOMY
        return False
    except:
        return False

def get_category_suggestions(query, limit=10):
    """Get category suggestions for autocomplete/search."""
    from .fashion_taxonomy import FASHION_TAXONOMY
    
    if not query or len(query) < 2:
        return []
    
    suggestions = []
    query_lower = query.lower()
    
    def search_taxonomy(taxonomy, parent_path=''):
        for key, value in taxonomy.items():
            current_path = f"{parent_path}.{key}" if parent_path else key
            
            # Check if current key matches
            if query_lower in key.lower() or query_lower in format_category_name(key).lower():
                suggestions.append({
                    'path': current_path,
                    'name': format_category_name(key),
                    'display_path': get_category_display_name(current_path)
                })
            
            # Search nested structures
            if isinstance(value, dict):
                search_taxonomy(value, current_path)
            elif isinstance(value, list):
                for item in value:
                    item_path = f"{current_path}.{item}"
                    if query_lower in item.lower() or query_lower in format_category_name(item).lower():
                        suggestions.append({
                            'path': item_path,
                            'name': format_category_name(item),
                            'display_path': get_category_display_name(item_path)
                        })
    
    search_taxonomy(FASHION_TAXONOMY)
    
    # Sort by relevance and limit results
    suggestions = sorted(suggestions, key=lambda x: (
        0 if query_lower in x['name'].lower() else 1,  # Exact matches first
        len(x['name']),  # Shorter names first
        x['name'].lower()  # Alphabetical
    ))[:limit]
    
    return suggestions

# End custom semantic fashion taxonomy (see fashion_taxonomy.py)




def get_category_ids_for_keyword(keyword):
    """
    Get category IDs that should be searched when a keyword is detected.
    Returns empty list if no categories match.
    """
    keyword_lower = keyword.lower().strip()
    return KEYWORD_CATEGORY_MAPPINGS.get(keyword_lower, [])


def create_categories():
    category_names = []
    unique_top_level_categories = [] 
    
     # Fetch all sizes in a single query
    size_fields = [
        'size', 'women_size', 'us_shoe_size', 'shoe_size_width', 'hat_size' 'chest_size', 'waist_size', 'inseam', 'hip_size', 
        'waist_to_hem', 'shoulder_to_shoulder', 'shoulder_to_hem', 'ring_size', 'necklace_length', 'item_length', 'bottoms_size'
    ]
    
     # Display-friendly mapping for categories
    category_display_names = {
        'size': 'Clothing Size',  # Display name for 'size'
        'women_size': 'Clothing Size', 
        'bottoms_size': 'Pants & Shorts Size',
        'us_shoe_size': 'Shoe Size (US)', 
        'shoe_size_width': 'Shoe Width',
        'hat_size': 'Head Circumference',
        'chest_size': 'Bust Size',
        'waist_size': 'Waist Size',
        'inseam': 'Inseam',
        'hip_size': 'Hip Size',
        'waist_to_hem': 'Waist to Hem',
        'bra_size': 'Bra Size',
        'shoulder_to_shoulder': 'Shoulder to Shoulder',
        'shoulder_to_hem': 'Shoulder to Hem',
        'ring_size': 'Ring Size',
        'necklace_length': 'Necklace Length',
        'item_length': 'Jewelry Size',
    }

    clothing_subgroups = {
        "Outerwear": ["Jackets", "Suits & Sets"],
        "Dresses & Jumpsuits": ["Dresses", "Jumpsuits"],
        "Tops": ["Tops", "Sweaters"],
        "Bottoms": ["Jeans", "Pants", "Skirts", "Shorts"],
        "Outfits & Sets": ["Matching Set"],
        "Other": ["Other Clothing"]
    }
    # Fetch all sizes in a single query
    size_fields = list(category_display_names.keys()) 

    # Fetch available sizes from the database for the relevant fields
    available_sizes_queryset = CoreEbayitem.objects.filter(availability='IN_STOCK').values(*size_fields)
    

    # Get unique, non-null size values for each category
    available_sizes = {
        category: sorted(set(
            size.strip() for size in available_sizes_queryset.values_list(category, flat=True) if size and size.strip()
        ))
        for category in size_fields
    }

    # Split sizes properly before passing them to the template
    for category, sizes in available_sizes.items():
        unique_sizes = sorted(set(size for s in sizes for size in s.split() if s))
        available_sizes[category] = unique_sizes

    # Create a mapping of us_shoe_size to shoe_size_width
    shoe_size_width_mapping = {}
    for item in available_sizes_queryset:
        us_shoe_size = item.get('us_shoe_size')
        shoe_size_width = item.get('shoe_size_width')
        if us_shoe_size and shoe_size_width:
            if us_shoe_size not in shoe_size_width_mapping:
                shoe_size_width_mapping[us_shoe_size] = set()
            shoe_size_width_mapping[us_shoe_size].add(shoe_size_width)

    # Convert sets to lists for JSON serialization
    shoe_size_width_mapping = {k: list(v) for k, v in shoe_size_width_mapping.items()}

    try:
        database_category_ids = set(CoreEbayitem.objects.filter(availability='IN_STOCK').values_list('categoryId', flat=True))
        json_file_path = os.path.join(settings.BASE_DIR, 'finde', 'ebay_category_ids.json')

        # Load and filter categories from JSON
        with open(json_file_path, 'r') as f:
            category_data = json.load(f)

            # Filter category names based on category IDs present in the database
            category_rename_map = {
                "74962": ("Bags, Handbags & Cases", "Purses"),
                "169291": ("Women's Bags & Handbags", "Women's Bags & Handbags"), 
                "965": ("Other Women's Vintage Clothing", "Other Clothing"),
                "260011": ("Outfits & Sets", "Matching Set"),
                "182055": ("Slips & Petticoats", "Slips"),
                "175789": ("Sleepwear & Robes", "Loungewear"),
                "182056": ("Other Vintage Lingerie", "Other Loungewear & Lingerie"),
                "74976": ("Women's Vintage Shoes", "Uncategorized"),
                "175819": ("Vintage Hair Accessories", "Hair"),
                "175783": ("Coats, Jackets & Vests", "Jackets"),
                "175792": ("Suits, Sets & Suit Separates", "Suits & Sets"),
                "175787": ("Jumpsuits & Playsuits", "Jumpsuits"),
                "262011": ("Jewelry Sets", "Sets"),
                "262014": ("Rings", "Rings"),
                "262008": ("Earrings", "Earrings"),
                "262003": ("Bracelets & Charms", "Bracelets"),
                "262013": ("Necklaces & Pendants", "Necklaces"),
                "166734": ("Other Vintage & Antique Jewelry", "Other Jewelry"),
                "175807": ("Scarves & Wraps", "Scarves"),
                "74969": ("Women's Hats", "Hats"),
                "957": ("Other Vintage Accessories", "Other Accessories"),
                "175769": ("Wallets & Coin Purses", "Wallets"),
                "45333": ("Flats", "Flats"),
                "95672": ("Athletic Shoes", "Sneakers"),
                "111": ("Loafers", "Loafers"), # Loafers (custom category ID; eBay has no 'Loafers' category)  
                "222": ("Wedges", "Wedges"),# Wedges (custom category ID; eBay has no 'Wedges' category)
                # IMPORTANT: if addeding custom categories, also add the categoryids to the list array below this code: custom_categories = [...categoryids...]
            }

        # Get ALL category IDs for dropdown
        all_database_category_ids = set(CoreEbayitem.objects.values_list('categoryId', flat=True).distinct())

        # Create separate category list for IN_STOCK categories
        seen_category_ids = set()
        category_names = []

        # Create separate category list for ALL categories
        all_category_names = []

        # Process category data and prevent duplicate category names
         # Process each category only ONCE
        for item in category_data:
            category_id = item['categoryId']
            
            # Skip if we've already processed this category
            if category_id in seen_category_ids:
                continue
                
            # Only process categories that exist in our database
            if category_id not in all_database_category_ids:
                continue
                
            # Mark as processed
            seen_category_ids.add(category_id)
            
            # Build category info once
            category_name = category_rename_map.get(category_id, (None, item['categoryName']))[1]
            top_level_category = next(
                (key for key, ids in CATEGORY_MAPPINGS.items() if category_id in ids),
                "Miscellaneous"
            )
            category_info = {
                'id': category_id,
                'name': category_name,
                'top_level_category': top_level_category
            }
            
            # Add to ALL categories list
            all_category_names.append(category_info)
            
            # Also add to IN_STOCK categories list if it's in stock
            if category_id in database_category_ids:
                category_names.append(category_info)
        
        

         # ADD CUSTOM CATEGORIES SEPARATELY
        custom_categories = ["111", "222"]  # Custom category IDs
        
        for category_id in custom_categories:
            if category_id not in seen_category_ids:  # Only check if not already processed
                seen_category_ids.add(category_id)
                category_name = category_rename_map.get(category_id, (None, f"Category {category_id}"))[1]
                top_level_category = next(
                    (key for key, ids in CATEGORY_MAPPINGS.items() if category_id in ids),
                    "Shoes"  # Default to "Shoes" since these are shoe categories
                )
                
                # Always add to all_category_names
                all_category_names.append({
                    'id': category_id,
                    'name': category_name,
                    'top_level_category': top_level_category
                })
                
                # Always add to category_names (remove the database check)
                category_names.append({
                    'id': category_id,
                    'name': category_name,
                    'top_level_category': top_level_category
                })

        category_names = sorted(category_names, key=lambda x: x['name'])
        unique_top_level_categories = sorted({category['top_level_category'] for category in category_names})

    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Error: {str(e)}")

           
    return category_names, all_category_names, unique_top_level_categories, available_sizes, category_display_names, clothing_subgroups, shoe_size_width_mapping

@require_POST
@admin_required
def delete_selected_items(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            item_ids = data.get('item_ids', [])
            deleted_item_ids = []

            for item_id in item_ids:
                # Retrieve the item from CoreEbayitem
                item = CoreEbayitem.objects.filter(item_id=item_id).first()
                
                # If the item exists, delete its media file
                if item:
                    logger.debug(f"Found item: {item}")

                    # Check if the item has a related shoe_size_conversion
                    if item.shoe_size_conversion_id:
                        # Retrieve the associated ShoeSizeConversion
                        shoe_size_conversion = ShoeSizeConversion.objects.filter(id=item.shoe_size_conversion_id).first()
                        
                        # If ShoeSizeConversion exists, delete it
                        if shoe_size_conversion:
                            logger.debug(f"Found and deleting ShoeSizeConversion: {shoe_size_conversion}")
                            shoe_size_conversion.delete()

                    if hasattr(item, 'gallery_url') and item.gallery_url:
                        if settings.EBAY_ENV == 'sandbox':
                            # delete image from local media folder
                            local_path = os.path.join(settings.MEDIA_ROOT, item.gallery_url)
                            logger.debug(f"Deleting local file: {local_path}")
                            if os.path.isfile(local_path):
                                os.remove(local_path)
                        else:
                            # delete image from S3 bucket
                            s3_path = item.gallery_url  # e.g. "webp_images/foo.webp"
                            logger.debug(f"Deleting S3 file: {s3_path}")
                            if default_storage.exists(s3_path):
                                default_storage.delete(s3_path)
                    else:
                        logger.debug(f"Item {item_id} has no gallery_url attribute.")
                        
                    # Delete the item from the database
                    item.delete()
                    deleted_item_ids.append(item_id)

                # Similarly, handle items from CoreEbayitemSold
                sold_item = CoreEbayitemSold.objects.filter(item_id=item_id).first()
                if sold_item:
                    logger.debug(f"Found sold item: {sold_item}")
                    if hasattr(sold_item, 'gallery_url'):
                        sold_media_file_path = os.path.join(settings.MEDIA_ROOT, sold_item.gallery_url)  # Use MEDIA_ROOT instead of MEDIA_URL
                        logger.debug(f"Attempting to delete sold file at: {sold_media_file_path}")
                        if os.path.isfile(sold_media_file_path):
                            os.remove(sold_media_file_path)  # Delete the file from the filesystem
                        else:
                            logger.warning(f"Sold file not found: {sold_media_file_path}")
                    else:
                        logger.debug(f"Sold item {item_id} has no gallery_url attribute.")
                        
                    # Delete the sold item from the database
                    sold_item.delete()
                    deleted_item_ids.append(item_id)

            logger.debug('Received item IDs: %s', item_ids)  # For debugging
            logger.debug('Deleted items: %s', deleted_item_ids)  # For debugging

            return JsonResponse({'status': 'success', 'deleted_item_ids': deleted_item_ids}, status=200)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=400)
    
def make_username_unique(username):
    original_username = username
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{original_username}{counter}"
        counter += 1
    return username

@admin_required
def update_availability_status_view(request):
    # Fetch items from database
    db_items = CoreEbayitem.objects.all()

    # corresponds to models.py coreEbayItem class
    for item in db_items:
        try:
            item.update_availability_status()
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return JsonResponse({'status': 'success'})