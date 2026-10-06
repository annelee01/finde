"""OpenSearch query building, size filtering and the browse page."""

import logging
from urllib.parse import parse_qs, unquote

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from opensearchpy import connections

from ..curated_filters import CURATED_FILTERS
from ..documents import CoreEbayitemDocument
from ..maps_and_terms import PANTS_TERMS, SIZE_ABBR_MAP, SHOE_CATEGORY_IDS
from ..models import CoreEbayitem
from ..size_sorting import sort_sizes
from ..utils import (
    PRECISE_COLOR_TERMS,
    normalize_colors,
    get_color_variants_for_search,
    get_all_color_variants_for_normalized,
    calculate_time_since_update,
    create_categories,
    CATEGORY_MAPPINGS,
    get_category_ids_for_keyword,
)

logger = logging.getLogger(__name__)


# Define which category groups can have size filters applied
SIZE_APPLICABLE_CATEGORIES = {
    "Shoes": {
        "categories": CATEGORY_MAPPINGS["Shoes"],
        "size_fields": ["us_shoe_size", "shoe_size_width"]
    },
    "Clothing": {
        "categories": CATEGORY_MAPPINGS["Clothing"],
        "size_fields": ["chest_size","waist_size", "hip_size", "waist_to_hem", "shoulder_to_shoulder", "shoulder_to_hem", "women_size", "size"],

        # Nested structure for specific categories within clothing
        "category_specific_sizes": {
            # Pants & shorts categories
            "175796": ["bottoms_size", "waist_size", "hip_size", "waist_to_hem", "inseam"],  # Pants
            "63863": ["bottoms_size", "waist_size", "hip_size", "waist_to_hem", "inseam"],   # Pants (women's, mod)
            "175785": ["bottoms_size", "waist_size", "hip_size", "waist_to_hem", "inseam"],  # Jeans
            "11554": ["bottoms_size", "waist_size", "hip_size", "waist_to_hem", "inseam"],   # Jeans (women's, mod)
            "175790": ["bottoms_size", "waist_size", "hip_size", "waist_to_hem", "inseam"],  # Shorts
            "11555": ["bottoms_size", "waist_size", "hip_size", "waist_to_hem", "inseam"],   # Shorts (women's, mod)

            # Skirt categories
            "175791": ["size", "waist_size"],  # Skirts
            "63864": ["size", "waist_size"],   # Skirts (women's, mod)

            # Shirt categories
            "175784": ["size", "chest_size"],  # Shirts & Tops
            "63861": ["size", "chest_size"],   # Shirts & Tops (women's, mod)
            "175792": ["size", "chest_size"],  # T-Shirts
            "63865": ["size", "chest_size"],   # T-Shirts (women's, mod)

            # Suit categorie
            "175792": ["size", "chest_size", "waist_size", "hip_size", "waist_to_hem", "shoulder_to_shoulder", "shoulder_to_hem", "inseam"],   # Suits, Sets & Suit Separates
            "63865": ["size", "chest_size", "waist_size", "hip_size", "waist_to_hem", "shoulder_to_shoulder", "shoulder_to_hem", "inseam"],     # Suits & Suit Separates (women's, mod)

            # Dress categories
            "175795": ["size", "waist_size", "chest_size"],  # Dresses
            "53159": ["size", "waist_size", "chest_size"],   # Dresses (women's, mod)

            # Other categories use all general clothing size fields
            # Any category not listed above will use the default size_fields
        }
    },
    "Jewelry": {
        "categories": CATEGORY_MAPPINGS["Jewelry"],
        "size_fields": ["ring_size", "item_length", "necklace_length"],
        # Nested structure for specific categories within jewelry
        "category_specific_sizes": {
            # Ring categories - only use ring_size
            "262014": ["ring_size"],  # Rings

            # Necklace categories - use necklace_length and item_length
            "262013": ["necklace_length", "item_length"],  # Necklaces & Pendants
            "262003": ["item_length"],  # Bracelets & Charms

            # Other jewelry categories use general item_length
            # Any category not listed above will use the default size_fields
        }
    },
    "Loungewear & Lingerie": {
        "categories": CATEGORY_MAPPINGS["Loungewear & Lingerie"],
        "size_fields": ["size", "chest_size"]
    }
}

# Categories that don't have size restrictions
NON_SIZE_CATEGORIES = CATEGORY_MAPPINGS["Bags & Purses"] + CATEGORY_MAPPINGS["Accessories"] + CATEGORY_MAPPINGS["Jewelry"]

def get_category_group_for_id(category_id):
    """Determine which category group a category ID belongs to"""
    category_id_str = str(category_id)

    logger.debug(f"get_category_group_for_id: Looking for category_id: {category_id_str}")

    for group_name, group_data in SIZE_APPLICABLE_CATEGORIES.items():
        logger.debug(f"get_category_group_for_id: Checking group {group_name} with categories: {group_data['categories']}")
        if category_id_str in group_data["categories"]:
            logger.debug(f"get_category_group_for_id: Found {category_id_str} in group {group_name}")
            return group_name

    # Check NON_SIZE_CATEGORIES - convert to strings for comparison
    non_size_str = [str(cat) for cat in NON_SIZE_CATEGORIES]
    if category_id_str in non_size_str:
        logger.debug(f"get_category_group_for_id: Found {category_id_str} in NON_SIZE_CATEGORIES")
        return "non_size"

    logger.warning(f"get_category_group_for_id: Category {category_id_str} not found in any group")
    return None

def create_global_size_filters(size_groups):
    """
    Create size filters that apply globally (when no categories are specified)
    This will find items with the specified sizes and automatically include their categories
    """
    logger.debug(f"\n=== create_global_size_filters START ===")
    logger.debug(f"Input size_groups: {size_groups}")

    filters = []

    # Special handling for shoe sizes - combine both size and width into one filter
    shoe_size_values = size_groups.get('us_shoe_size', [])
    shoe_width_values = size_groups.get('shoe_size_width', [])

    logger.debug(f"Extracted shoe_size_values: {shoe_size_values}")
    logger.debug(f"Extracted shoe_width_values: {shoe_width_values}")

    if shoe_size_values or shoe_width_values:
        logger.debug(f"create_global_size_filters: Creating COMBINED shoe filter")
        logger.debug(f"  Calling create_shoe_size_filter with BOTH parameters:")
        logger.debug(f"    shoe_size_values: {shoe_size_values}")
        logger.debug(f"    shoe_width_values: {shoe_width_values}")

        shoe_filter = create_shoe_size_filter(shoe_size_values, shoe_width_values)
        if shoe_filter:
            filters.append(shoe_filter)
            logger.debug(f"  Added COMBINED shoe filter: {shoe_filter}")
        else:
            logger.debug(f"  create_shoe_size_filter returned None!")

    # Handle all other size fields (non-shoe)
    for size_field, size_values in size_groups.items():
        if not size_values:
            logger.warning(f"Skipping {size_field} - no values")
            continue

        # Skip shoe fields since we handled them above
        if size_field in ['us_shoe_size', 'shoe_size_width']:
            logger.warning(f"Skipping {size_field} - already handled in combined shoe filter")
            continue

        logger.debug(f"Processing non-shoe field: {size_field} with values: {size_values}")
        # Handle other size fields
        size_filter = create_generic_size_filter(size_field, size_values)
        if size_filter:
            filters.append(size_filter)
        else:
            logger.debug(f"create_generic_size_filter returned None for {size_field}")

    logger.debug(f"Final filters count: {len(filters)}")
    for i, filter_obj in enumerate(filters):
        logger.debug(f"Filter {i}: {filter_obj}")

    return filters

def create_category_specific_size_filters(all_category_ids, size_groups):
    """
    Create size filters that apply to specific category groups.
    Modified to handle cases where size filters should apply across different category types.
    """

    category_specific_filters = []

    # Convert category IDs to strings for consistency
    all_category_ids = [str(cat_id) for cat_id in all_category_ids]

    # Group selected categories by their category group
    selected_categories_by_group = {}
    categories_without_sizes = []

    for cat_id in all_category_ids:
        group = get_category_group_for_id(cat_id)

        if group and group != "non_size":
            if group not in selected_categories_by_group:
                selected_categories_by_group[group] = []
            selected_categories_by_group[group].append(cat_id)
        else:
            # This category doesn't have size restrictions
            categories_without_sizes.append(cat_id)

    # Check if we have size filters that don't match any of the selected category groups
    unmatched_size_filters = {}
    matched_groups = set()

    for size_field, size_values in size_groups.items():
        if not size_values:
            continue

        # Find which groups this size field belongs to
        field_found_in_groups = []
        for group_name, group_config in SIZE_APPLICABLE_CATEGORIES.items():
            # Check general size_fields
            if size_field in group_config["size_fields"]:
                field_found_in_groups.append(group_name)

            # ALSO CHECK category_specific_sizes
            category_specific_config = group_config.get("category_specific_sizes", {})
            for cat_id, allowed_fields in category_specific_config.items():
                if size_field in allowed_fields:
                    if group_name not in field_found_in_groups:
                        field_found_in_groups.append(group_name)
                    break

        # Check if any of these groups are in our selected categories
        group_matched = False
        size_field_can_be_applied = False

        for group in field_found_in_groups:
            if group in selected_categories_by_group:
                matched_groups.add(group)
                group_matched = True

                # Check if this size field can actually be applied to any category in this group
                group_config = SIZE_APPLICABLE_CATEGORIES[group]
                category_specific_config = group_config.get("category_specific_sizes", {})

                for cat_id in selected_categories_by_group[group]:
                    if cat_id in category_specific_config:
                        # Check if this specific category allows this size field
                        allowed_fields = category_specific_config[cat_id]
                        if size_field in allowed_fields:
                            size_field_can_be_applied = True
                            break
                        else:
                            logger.debug(f"Size field {size_field} NOT in allowed fields for category {cat_id}")
                    else:
                        # Category not in specific config, so it uses general size_fields
                        if size_field in group_config["size_fields"]:
                            size_field_can_be_applied = True
                            break
                        else:
                            logger.debug(f"Size field {size_field} not in general size_fields for category {cat_id}")

                if size_field_can_be_applied:
                    logger.debug(f"Size field {size_field} can be applied to group {group} - BREAKING")
                    break
                else:
                    logger.debug(f"Size field {size_field} cannot be applied to any category in group {group}")

        if not group_matched or not size_field_can_be_applied:
            # This size filter doesn't match any selected category groups OR can't be applied to any selected categories
            unmatched_size_filters[size_field] = size_values
        else:
            logger.debug(f"{size_field} will be handled as CATEGORY-SPECIFIC")


    # Handle each category group with size filters
    for group_name, category_ids in selected_categories_by_group.items():

        group_config = SIZE_APPLICABLE_CATEGORIES[group_name]
        applicable_size_fields = group_config["size_fields"]

        # IMPORTANT: Collect ALL applicable fields (general + category-specific)
        all_applicable_fields = set(applicable_size_fields)

        # Add fields from category_specific_sizes for selected categories
        category_specific_config = group_config.get("category_specific_sizes", {})
        for cat_id in category_ids:
            if cat_id in category_specific_config:
                specific_fields = category_specific_config[cat_id]
                all_applicable_fields.update(specific_fields)

        # Check if any size filters apply to this group
        group_size_filters = []
        for size_field in all_applicable_fields:  # Check ALL fields, not just general ones
            logger.debug(f"Checking if size field {size_field} applies to group {group_name}")

            # Skip fields that are in unmatched_size_filters (they'll be handled globally)
            if size_field in unmatched_size_filters:
                logger.warning(f"SKIPPING {size_field} - it's in unmatched filters")
                continue

            if size_field in size_groups:
                logger.debug(f"{size_field} found in size_groups with values: {size_groups[size_field]}")
            else:
                logger.warning(f"{size_field} NOT found in size_groups")
                continue

            if size_field in size_groups and size_groups[size_field]:
                if group_name == "Shoes":
                    # Special shoe logic (existing code)
                    shoe_filter = create_shoe_size_filter(
                        size_groups.get('us_shoe_size', []),
                        size_groups.get('shoe_size_width', [])
                    )
                    if shoe_filter:
                        group_size_filters.append(shoe_filter)
                        logger.debug(f"Added shoe filter to group_size_filters")
                        break  # Don't add duplicate shoe filters
                else:
                    # Generic size filter for other categories
                    size_filter = create_generic_size_filter(size_field, size_groups[size_field])
                    if size_filter:
                        group_size_filters.append(size_filter)
                    else:
                        logger.debug(f"generic_size_filter returned None for {size_field}")

        for i, filter_obj in enumerate(group_size_filters):
            logger.debug(f"group_size_filter[{i}]: {filter_obj}")

        # Handle category-specific size restrictions
        if group_size_filters:
            # Split categories into those with specific size restrictions and those without
            categories_with_specific_sizes = []
            categories_with_general_sizes = []

            for cat_id in category_ids:
                if cat_id in category_specific_config:
                    categories_with_specific_sizes.append(cat_id)
                else:
                    categories_with_general_sizes.append(cat_id)

            # Create separate filters for each category with specific size restrictions
            specific_category_filters = []
            categories_with_no_applicable_sizes = []

            for cat_id in categories_with_specific_sizes:

                allowed_size_fields = category_specific_config[cat_id]

                # Create size filters only for allowed fields for this category
                category_size_filters = []
                for size_field, size_values in size_groups.items():
                    if size_field in allowed_size_fields and size_values:
                        size_filter = create_generic_size_filter(size_field, size_values)
                        if size_filter:
                            category_size_filters.append(size_filter)
                        else:
                            logger.debug(f"size_filter returned None for {size_field}")
                    else:
                        if size_field not in allowed_size_fields:
                            logger.debug(f"{size_field} NOT ALLOWED for category {cat_id}")
                        if not size_values:
                            logger.debug(f"{size_field} has no values")

                if category_size_filters:
                    # Create filter for this specific category + its allowed size filters
                    if len(category_size_filters) == 1:
                        category_filter = {
                            "bool": {
                                "must": [
                                    {"term": {"categoryId": int(cat_id)}},
                                    category_size_filters[0]
                                ]
                            }
                        }
                    else:
                        # Use AND logic for multiple size filters
                        category_filter = {
                            "bool": {
                                "must": [
                                    {"term": {"categoryId": int(cat_id)}}
                                ] + category_size_filters
                            }
                        }

                    specific_category_filters.append(category_filter)
                else:
                    # No applicable size filters for this category - add to unrestricted list
                    categories_with_no_applicable_sizes.append(cat_id)

            # Handle categories with general size restrictions
            if categories_with_general_sizes:
                # Use AND logic for general categories too
                if len(group_size_filters) == 1:
                    general_filter = {
                        "bool": {
                            "must": [
                                {"terms": {"categoryId": [int(cat_id) for cat_id in categories_with_general_sizes]}},
                                group_size_filters[0]
                            ]
                        }
                    }
                else:
                    # Use AND logic for multiple size filters
                    general_filter = {
                        "bool": {
                            "must": [
                                {"terms": {"categoryId": [int(cat_id) for cat_id in categories_with_general_sizes]}}
                            ] + group_size_filters
                        }
                    }

                specific_category_filters.append(general_filter)

            # Add categories with no applicable sizes to unrestricted list
            if categories_with_no_applicable_sizes:
                categories_without_sizes.extend(categories_with_no_applicable_sizes)

            # Add all specific category filters to the main list
            category_specific_filters.extend(specific_category_filters)

        else:
            # No size filters for this group, add categories to unrestricted list
            categories_without_sizes.extend(category_ids)


    # Handle unmatched size filters by creating global filters for any category
    if unmatched_size_filters:

        global_size_filters = []
        for size_field, size_values in unmatched_size_filters.items():
            if size_field == 'us_shoe_size':
                shoe_filter = create_shoe_size_filter(size_values, [])
                if shoe_filter:
                    global_size_filters.append(shoe_filter)
            elif size_field == 'shoe_size_width':
                width_filter = create_shoe_size_filter([], size_values)
                if width_filter:
                    global_size_filters.append(width_filter)
            else:
                size_filter = create_generic_size_filter(size_field, size_values)
                if size_filter:
                    global_size_filters.append(size_filter)

        if global_size_filters:
            # Add global size filter (no category restriction)
            if len(global_size_filters) == 1:
                global_size_only_filter = global_size_filters[0]
            else:
                global_size_only_filter = {
                    "bool": {
                        "should": global_size_filters,
                        "minimum_should_match": 1
                    }
                }

            category_specific_filters.append(global_size_only_filter)
    else:
        logger.debug(f"No unmatched_size_filters to process")

    # Add filter for categories without size restrictions
    if categories_without_sizes:
        unrestricted_filter = {"terms": {"categoryId": [int(cat_id) for cat_id in categories_without_sizes]}}
        category_specific_filters.append(unrestricted_filter)

    for i, filter_obj in enumerate(category_specific_filters):
        logger.debug(f"Final filter[{i}]: {filter_obj}")

    return category_specific_filters

def create_shoe_size_filter(shoe_size_values, shoe_width_values):
    """Create the shoe size filter logic with extensive debugging"""

    logger.debug(f"\n=== create_shoe_size_filter START ===")
    logger.debug(f"Input shoe_size_values: {shoe_size_values}")
    logger.debug(f"Input shoe_width_values: {shoe_width_values}")
    logger.debug(f"shoe_size_values type: {type(shoe_size_values)}")
    logger.debug(f"shoe_width_values type: {type(shoe_width_values)}")
    logger.debug(f"shoe_size_values bool: {bool(shoe_size_values)}")
    logger.debug(f"shoe_width_values bool: {bool(shoe_width_values)}")

    if not shoe_size_values and not shoe_width_values:
        logger.debug("create_shoe_size_filter: No size values provided, returning None")
        return None

    if shoe_size_values and shoe_width_values:
        logger.debug(f"Both size and width provided - creating combinations")
        shoe_combinations = []
        for shoe_size in shoe_size_values:
            for shoe_width in shoe_width_values:
                logger.debug(f"Creating combination for size='{shoe_size}' and width='{shoe_width}'")
                combination = {
                    "bool": {
                        "must": [
                            {"match_phrase": {"us_shoe_size": shoe_size}},
                            {"match_phrase": {"shoe_size_width": shoe_width}}
                        ]
                    }
                }
                shoe_combinations.append(combination)
                logger.debug(f"Added combination: {combination}")

        if len(shoe_combinations) == 1:
            result = shoe_combinations[0]
            logger.debug(f"Single combination result: {result}")
        else:
            result = {
                "bool": {
                    "should": shoe_combinations,
                    "minimum_should_match": 1
                }
            }
            logger.debug(f"Multiple combinations result: {result}")
        logger.debug(f"=== create_shoe_size_filter END ===\n")
        return result

    elif shoe_size_values:
        logger.debug(f"Only size values provided")
        if len(shoe_size_values) == 1:
            result = {"match_phrase": {"us_shoe_size": shoe_size_values[0]}}
            logger.debug(f"Single size result: {result}")
        else:
            result = {
                "bool": {
                    "should": [{"match_phrase": {"us_shoe_size": size}} for size in shoe_size_values],
                    "minimum_should_match": 1
                }
            }
            logger.debug(f"Multiple sizes result: {result}")
        logger.debug(f"=== create_shoe_size_filter END ===\n")
        return result

    elif shoe_width_values:
        logger.debug(f"Only width values provided")
        if len(shoe_width_values) == 1:
            result = {"match_phrase": {"shoe_size_width": shoe_width_values[0]}}
            logger.debug(f"Single width result: {result}")
        else:
            result = {
                "bool": {
                    "should": [{"match_phrase": {"shoe_size_width": width}} for width in shoe_width_values],
                    "minimum_should_match": 1
                }
            }
            logger.debug(f"Multiple widths result: {result}")
        logger.debug(f"=== create_shoe_size_filter END ===\n")
        return result

    logger.debug(f"=== create_shoe_size_filter END (no conditions met) ===\n")
    return None

def create_generic_size_filter(size_field, size_values):
    """Create a generic size filter for any size field"""

    if not size_values:
        return None

    if len(size_values) == 1:
        result = {"match_phrase": {size_field: size_values[0]}}
    else:
        result = {
            "bool": {
                "should": [{"match_phrase": {size_field: size_value}} for size_value in size_values],
                "minimum_should_match": 1
            }
        }

    return result


def get_curated_filters_config(request):
    """API endpoint to serve curated filter configs to frontend"""
    return JsonResponse({
        'curated_filters': CURATED_FILTERS
    })


# Opensearch search items & display results with pagination
def opensearch_results(request):

    # Create search object for all items by default
    search = CoreEbayitemDocument.search()

    # Start with a bool query
    bool_query = {
        "bool": {
            "must": [],
            "filter": [
                # Always add availability filter first
                {"term": {"availability": "IN_STOCK"}}
            ]
        }
    }

   # Handle basic query search
    query = request.GET.get('query', '').strip()

    # *** Check for curated filter parameter ***
    curated_filter_name = request.GET.get('curated_filter')

    curated_config = None

    if curated_filter_name and curated_filter_name in CURATED_FILTERS:
        curated_config = CURATED_FILTERS[curated_filter_name]

    # *** HANDLE CURATED FILTERS WITH SPECIAL OR LOGIC ***
    if curated_config:
        # STEP 1: Get curated terms from config
        curated_terms = []
        if curated_config.get('keywords'):
            curated_terms.extend(curated_config['keywords'])
        if curated_config.get('materials'):
            curated_terms.extend(curated_config['materials'])
        if curated_config.get('brands'):
            curated_terms.extend(curated_config['brands'])

        # Get exclusion terms
        exclude_keywords = curated_config.get('exclude_keywords', [])
        exclude_colors = curated_config.get('exclude_colors', [])

        # STEP 2: Handle query if present, otherwise just apply curated filter
        if query:
            # User provided additional search terms with the curated filter
            search_terms = query.split()
            user_terms = []
            matched_curated_terms = []

            # Convert curated terms to lowercase for comparison
            curated_terms_lower = [term.lower() for term in curated_terms]

            for term in search_terms:
                term_lower = term.lower()
                # Check if this term is in our curated list
                is_curated = any(
                    curated_term.lower() in term_lower or term_lower in curated_term.lower()
                    for curated_term in curated_terms_lower
                )

                if is_curated:
                    matched_curated_terms.append(term)
                else:
                    user_terms.append(term)

            # Create AND logic between user query and curated filter
            must_queries = []

            # Add user query as a MUST clause
            if user_terms:
                for user_term in user_terms:
                    user_term_queries = []

                    # Basic field searches
                    user_term_queries.extend([
                        {"match": {"title": {"query": user_term, "boost": 2.0}}},
                        {"match": {"color": user_term}},
                        {"match": {"brand": user_term}},
                        {"match": {"material": user_term}},
                        {"match": {"size": user_term}},
                        {"match": {"us_shoe_size": user_term}},
                        {"match": {"waist_size": user_term}},
                        {"match": {"bottoms_size": user_term}}
                    ])

                    # Add category matching for user terms
                    category_ids_for_keyword = get_category_ids_for_keyword(user_term)
                    if category_ids_for_keyword:
                        try:
                            int_category_ids = [int(cat_id) for cat_id in category_ids_for_keyword]
                            user_term_queries.append({
                                "terms": {"categoryId": int_category_ids}
                            })
                        except ValueError as e:
                            logger.error(f"Category ID conversion error for '{user_term}': {e}")

                    # Each user term must match at least one field
                    user_term_must = {
                        "bool": {
                            "should": user_term_queries,
                            "minimum_should_match": 1
                        }
                    }
                    must_queries.append(user_term_must)

        # STEP 3: Apply curated filter (with or without user query)
        curated_should_queries = []

        # Use ALL curated terms
        for curated_term in curated_terms:
            curated_should_queries.extend([
                {"match": {"title": curated_term}},
                {"match": {"brand": {"query": curated_term, "boost": 3.0}}},  # Higher boost for brand
                {"match": {"material": curated_term}}
            ])

            # Add category matching for curated terms
            category_ids_for_keyword = get_category_ids_for_keyword(curated_term)
            if category_ids_for_keyword:
                try:
                    int_category_ids = [int(cat_id) for cat_id in category_ids_for_keyword]
                    curated_should_queries.append({
                        "terms": {"categoryId": int_category_ids}
                    })
                except ValueError as e:
                    logger.error(f"Category ID conversion error for '{curated_term}': {e}")

        # Curated filter: must match at least one curated term
        if curated_should_queries:
            curated_must_query = {
                "bool": {
                    "should": curated_should_queries,
                    "minimum_should_match": 1
                }
            }

            # If we have user queries, combine them with curated filter
            if query and 'must_queries' in locals() and must_queries:
                must_queries.append(curated_must_query)
                combined_must_query = {
                    "bool": {
                        "must": must_queries
                    }
                }
                bool_query["bool"]["must"].append(combined_must_query)
            else:
                # No user query, just apply curated filter
                bool_query["bool"]["must"].append(curated_must_query)

        # STEP 4: Handle exclusions
        must_not_queries = []

        # Add exclude_keywords logic
        if exclude_keywords:
            for exclude_term in exclude_keywords:
                exclude_queries = []

                exclude_queries.extend([
                    {"match": {"title": exclude_term}},
                    {"match": {"color": exclude_term}},
                    {"match": {"brand": exclude_term}},
                    {"match": {"material": exclude_term}}
                ])

                exclude_category_ids = get_category_ids_for_keyword(exclude_term)
                if exclude_category_ids:
                    try:
                        int_exclude_category_ids = [int(cat_id) for cat_id in exclude_category_ids]
                        exclude_queries.append({
                            "terms": {"categoryId": int_exclude_category_ids}
                        })
                    except ValueError as e:
                        logger.error(f"Exclude category ID conversion error for '{exclude_term}': {e}")

                exclude_query = {
                    "bool": {
                        "should": exclude_queries,
                        "minimum_should_match": 1
                    }
                }
                must_not_queries.append(exclude_query)

        # Add all must_not queries
        if must_not_queries:
            if "must_not" not in bool_query["bool"]:
                bool_query["bool"]["must_not"] = []
            bool_query["bool"]["must_not"].extend(must_not_queries)

        # STEP 5: Apply curated categories and colors
        curated_categories = []
        if curated_config.get('categories'):
            for category_list in curated_config['categories'].values():
                if isinstance(category_list, list):
                    curated_categories.extend(category_list)

        if curated_categories:
            try:
                int_category_ids = [int(cat_id) for cat_id in curated_categories]
                category_filter = {"terms": {"categoryId": int_category_ids}}
                bool_query["bool"]["filter"].append(category_filter)
            except ValueError as e:
                logger.error(f"Curated category ID conversion error: {e}")

        # Apply curated colors
        curated_colors = []
        if curated_config.get('colors'):
            curated_colors = [color.lower() for color in curated_config['colors']]

        # Apply curated colors as additional filters
        if curated_colors:
            color_queries = []
            for color_filter in curated_colors:
                color_query = {
                    "bool": {
                        "should": [
                            {"term": {"color.keyword": color_filter}},
                            {"match": {"color": {"query": color_filter, "operator": "and"}}},
                        ],
                        "minimum_should_match": 1
                    }
                }

                # Add color variants
                normalized_variants = get_all_color_variants_for_normalized(color_filter)
                for variant in normalized_variants:
                    if variant != color_filter:
                        color_query["bool"]["should"].extend([
                            {"term": {"color.keyword": variant}},
                            {"match": {"color": {"query": variant, "operator": "and"}}}
                        ])

                color_queries.append(color_query)

            # Combine color queries with OR logic
            if len(color_queries) == 1:
                final_color_filter = color_queries[0]
            else:
                final_color_filter = {
                    "bool": {
                        "should": color_queries,
                        "minimum_should_match": 1
                    }
                }

            bool_query["bool"]["filter"].append(final_color_filter)

        # STEP 6.5: Add exclude_colors logic
        if exclude_colors:
            exclude_color_queries = []

            for exclude_color in exclude_colors:
                exclude_color = exclude_color.lower()

                # Create exclusion for this color and all its variants
                color_exclusions = [
                    {"term": {"color.keyword": exclude_color}},
                    {"match": {"color": {"query": exclude_color, "operator": "and"}}}
                ]

                # Add all color variants to exclusion
                normalized_variants = get_all_color_variants_for_normalized(exclude_color)
                for variant in normalized_variants:
                    if variant != exclude_color:
                        color_exclusions.extend([
                            {"term": {"color.keyword": variant}},
                            {"match": {"color": {"query": variant, "operator": "and"}}}
                        ])

                # Combine all exclusions for this color
                exclude_color_query = {
                    "bool": {
                        "should": color_exclusions,
                        "minimum_should_match": 1
                    }
                }
                exclude_color_queries.append(exclude_color_query)

            # Add all color exclusions to must_not
            # Ensure must_not key exists
            if "must_not" not in bool_query["bool"]:
                bool_query["bool"]["must_not"] = []
            bool_query["bool"]["must_not"].extend(exclude_color_queries)

    # *** HANDLE REGULAR SEARCH (NON-CURATED) WITH AND LOGIC ***
    # ONLY process this if NOT a curated filter
    elif query and not curated_config:
        search_terms = query.split()

        def get_size_variants(term):
            """Get all possible size variants for a given term using SIZE_ABBR_MAP"""
            term_lower = term.lower()
            variants = [term]  # Always include original term

            # Check SIZE_ABBR_MAP for abbreviation conversion
            for full_name, abbr in SIZE_ABBR_MAP.items():
                if term_lower == full_name.lower():
                    variants.append(abbr)
                    break
                elif term_lower == abbr.lower():
                    variants.append(full_name)
                    break

            # Remove duplicates and return
            final_variants = list(set(variants))
            return final_variants

        # For each search term, require it to be found in at least one field (AND logic)
        for term in search_terms:
            # Get size variants for this term
            size_variants = get_size_variants(term)

            # Get color variants for this term
            color_variants = get_color_variants_for_search(term)

            # NGet category IDs for this keyword
            category_ids_for_keyword = get_category_ids_for_keyword(term)

            # Create queries for this specific term
            term_queries = []

            # Text field queries (use match for partial matching)
            term_queries.extend([
                {"match": {"title": term}},
                {"match": {"color": term}},
                {"match": {"brand": term}},
                {"match": {"material": term}}
            ])

            # Add category-based queries if keyword matches categories
            if category_ids_for_keyword:
                # Convert string category IDs to integers if needed
                try:
                    int_category_ids = [int(cat_id) for cat_id in category_ids_for_keyword]
                    term_queries.append({
                        "terms": {"categoryId": int_category_ids}
                    })
                except ValueError:
                    # Keep as strings if conversion fails
                    term_queries.append({
                        "terms": {"categoryId": category_ids_for_keyword}
                    })

            # Add color variant queries
            for color_variant in color_variants:
                if color_variant != term:  # Don't duplicate the original term
                    # For precise color terms, only search title and material fields
                    if term.lower() in PRECISE_COLOR_TERMS:
                        # For precise color terms, emphasize title/material search, de-emphasize color field
                        term_queries.extend([
                            {"match": {"title": term}},
                            {"match": {"brand": term}},
                            {"match": {"material": term}}
                            # Note: NOT adding color field query for precise terms
                        ])
                    else:
                        # For non-precise terms, search all fields normally
                        term_queries.extend([
                            {"match": {"title": term}},
                            {"match": {"color": term}},
                            {"match": {"brand": term}},
                            {"match": {"material": term}}
                        ])

            # Size field queries (use match instead of term for analyzed fields)
            term_queries.extend([
                {"match": {"us_shoe_size": term}},
                {"match": {"waist_size": term}},
                {"match": {"size": term}},
                {"match": {"bottoms_size": term}}  # Added bottoms_size
            ])

            # Add size variant queries for SIZE_ABBR_MAP
            for variant in size_variants:
                if variant != term:  # Don't duplicate the original term
                    term_queries.extend([
                        {"match": {"us_shoe_size": variant}},
                        {"match": {"waist_size": variant}},
                        {"match": {"size": variant}},
                        {"match": {"bottoms_size": variant}}  # Added bottoms_size
                    ])

            # Special handling for 'shoe' term - also search in shoe categories
            if term.lower() in ['shoe', 'shoes']:
                # Add category filter for shoe categories
                term_queries.append({
                    "terms": {"categoryId": list(SHOE_CATEGORY_IDS)}
                })

            # Special handling for pants terms - also search for other pants terms
            if term.lower() in PANTS_TERMS:
                # Add queries for all other pants terms
                for pants_term in PANTS_TERMS:
                    if pants_term.lower() != term.lower():  # Don't duplicate the original term
                        term_queries.extend([
                            {"match": {"title": pants_term}},
                            {"match": {"color": pants_term}},
                            {"match": {"brand": pants_term}},
                            {"match": {"material": pants_term}}
                        ])

            # Each term must be found in at least one field
            term_query = {
                "bool": {
                    "should": term_queries,
                    "minimum_should_match": 1
                }
            }
            # Add to "must" array - this creates AND logic between terms
            bool_query["bool"]["must"].append(term_query)

    # Handle search_keyword - UPDATED to include all fields with match for sizes
    search_keyword = unquote(request.GET.get('search_keyword', '')).strip()

    if search_keyword:
        # Get category IDs for search keyword
        keyword_category_ids = get_category_ids_for_keyword(search_keyword)

        keyword_query = {
            "bool": {
                "should": [
                    {"multi_match": {"query": search_keyword, "fields": ["title", "brand", "color", "material"]}},
                    {"wildcard": {"title": f"*{search_keyword}*"}},
                    {"wildcard": {"brand": f"*{search_keyword}*"}},
                    {"wildcard": {"color": f"*{search_keyword}*"}},
                    {"wildcard": {"material": f"*{search_keyword}*"}},
                    # Use match for size matching (analyzed fields)
                    {"match": {"us_shoe_size": search_keyword}},
                    {"match": {"waist_size": search_keyword}},
                    {"match": {"size": search_keyword}},
                    {"match": {"bottoms_size": search_keyword}}  # Added bottoms_size
                ]
            }
        }

        # Add category-based query for search keyword
        if keyword_category_ids:
            try:
                int_category_ids = [int(cat_id) for cat_id in keyword_category_ids]
                keyword_query["bool"]["should"].append({
                    "terms": {"categoryId": int_category_ids}
                })
            except ValueError:
                keyword_query["bool"]["should"].append({
                    "terms": {"categoryId": keyword_category_ids}
                })

        # Add wildcard for singular form if keyword ends with 's'
        if search_keyword.endswith('s'):
            keyword_query["bool"]["should"].extend([
                {"wildcard": {"title": f"*{search_keyword[:-1]}*"}},
                {"wildcard": {"brand": f"*{search_keyword[:-1]}*"}},
                {"wildcard": {"color": f"*{search_keyword[:-1]}*"}},
                {"wildcard": {"material": f"*{search_keyword[:-1]}*"}}
            ])

        bool_query["bool"]["must"].append(keyword_query)



    # Handle color filtering - support multiple colors with OR logic (UPDATED for precise filtering)
    color_params = request.GET.getlist('color[]') + request.GET.getlist('color')

    # Also handle single parameter format (color without [])
    if not color_params:
        color_single = request.GET.get('color')
        if color_single:
            color_params = [color_single]

    if color_params:
        # Remove empty values and strip whitespace, also handle comma-separated values
        color_values = []
        for color_param in color_params:
            # Split by comma and strip whitespace for each value
            for color in color_param.split(','):
                if color.strip():
                    color_values.append(color.strip())

        if color_values:

            # Create OR condition for multiple colors
            color_queries = []
            for color_filter in color_values:

                # For color filtering, we want PRECISE matching of normalized colors
                # So "white" filter should only match items with color field = "white"
                # NOT items with "off white" in title

                color_query = {
                    "bool": {
                        "should": [
                            # ONLY search the color field with exact matching
                            {"term": {"color.keyword": color_filter}},  # Exact match if color is keyword field
                            {"match": {"color": {"query": color_filter, "operator": "and"}}},  # Analyzed field match
                        ],
                        "minimum_should_match": 1
                    }
                }

                # Also add variants that normalize TO this color
                # E.g., if filtering by "white", also include items categorized as "pearl", "bone", etc.
                # But NOT items that just mention these terms in title
                normalized_variants = get_all_color_variants_for_normalized(color_filter)
                for variant in normalized_variants:
                    if variant != color_filter:
                        color_query["bool"]["should"].extend([
                            {"term": {"color.keyword": variant}},
                            {"match": {"color": {"query": variant, "operator": "and"}}}
                        ])

                color_queries.append(color_query)

            # Combine all color queries with OR logic
            if len(color_queries) == 1:
                final_color_filter = color_queries[0]
            else:
                final_color_filter = {
                    "bool": {
                        "should": color_queries,
                        "minimum_should_match": 1
                    }
                }

            bool_query["bool"]["filter"].append(final_color_filter)


     # Handle price range filtering
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')

    if min_price or max_price:
        price_range = {}
        if min_price:
            price_range['gte'] = float(min_price)
        if max_price:
            price_range['lte'] = float(max_price)
        price_filter = {"range": {"price": price_range}}
        bool_query["bool"]["filter"].append(price_filter)

    # Handle category filtering
    all_category_ids = []
    category_params = request.GET.getlist('categoryId')

    for param in category_params:
        all_category_ids.extend([cat_id.strip() for cat_id in param.split(',') if cat_id.strip()])

    # Convert to integers
    try:
        all_category_ids = [int(cat_id) for cat_id in all_category_ids]
    except ValueError as e:
        logger.error(f"opensearch_results: Error converting category IDs: {e}")
        # Keep as strings if conversion fails
        pass


    # Handle size filtering with category-specific logic

    # Get the raw query string and parse it properly
    # Get the raw query string and parse it properly
    raw_query_string = request.META.get('QUERY_STRING', '')
    parsed_params = parse_qs(raw_query_string)

    # Extract size categories and values, handling repeated parameter names
    size_categories = parsed_params.get('size_category', [])
    size_values = parsed_params.get('size_value', [])

    # Also check for array notation
    size_categories.extend(parsed_params.get('size_category[]', []))
    size_values.extend(parsed_params.get('size_value[]', []))


    # Handle size filtering - now works with OR without categories
    if len(size_categories) == len(size_values) and size_categories:

        # Group size values by category
        size_groups = {}
        for i, (category, values) in enumerate(zip(size_categories, size_values)):
            if category not in size_groups:
                size_groups[category] = []
            # Handle comma-separated values within a single parameter
            for size_value in values.split(','):
                if size_value.strip():
                    size_groups[category].append(size_value.strip())


        if all_category_ids:

            # Create category-specific size filters
            category_specific_filters = create_category_specific_size_filters(all_category_ids, size_groups)


            if category_specific_filters:
                for i, filter_obj in enumerate(category_specific_filters):
                    logger.debug(f"Category specific filter {i}: {filter_obj}")

                # Use OR logic to combine all category-specific filters
                if len(category_specific_filters) == 1:
                    final_filter = category_specific_filters[0]
                    logger.debug(f"Using single category filter: {final_filter}")
                else:
                    final_filter = {
                        "bool": {
                            "should": category_specific_filters,
                            "minimum_should_match": 1
                        }
                    }

                bool_query["bool"]["filter"].append(final_filter)
            else:
                logger.debug(f"No category_specific_filters returned!")

        else:
            # No categories specified, create global size filters and auto-detect relevant categories
            global_size_filters = create_global_size_filters(size_groups)

            if global_size_filters:
                for i, filter_obj in enumerate(global_size_filters):
                    logger.debug(f"Global filter {i}: {filter_obj}")

                # If multiple size filters, combine with OR logic
                if len(global_size_filters) == 1:
                    bool_query["bool"]["filter"].append(global_size_filters[0])
                else:
                    # Create OR condition for multiple size filters
                    combined_filter = {
                        "bool": {
                            "should": global_size_filters,
                            "minimum_should_match": 1
                        }
                    }
                    bool_query["bool"]["filter"].append(combined_filter)
            else:
                logger.debug(f"No global_size_filters returned!")

    elif all_category_ids:
        # No size filters, just apply category filter normally
        category_filter = {"terms": {"categoryId": all_category_ids}}
        bool_query["bool"]["filter"].append(category_filter)


    # Apply the query to the search object
    search = search.query(bool_query)

    # Sorting
    sort_by = request.GET.get('sort_by', 'newlyAdded')
    has_search_terms = bool(query or search_keyword)
    curated_filter_name = request.GET.get('curated_filter')

    if sort_by == 'lowToHigh':
        search = search.sort({"price": {"order": "asc"}})
    elif sort_by == 'highToLow':
        search = search.sort({"price": {"order": "desc"}})
    elif sort_by == 'newlyAdded':
        # Always sort by ID for "newlyAdded", even with curated filters
        search = search.sort({"id": {"order": "desc"}})
    elif has_search_terms:
        # Only sort by score for explicit searches (not curated filters)
        search = search.sort("_score")
    else:
        search = search.sort({"id": {"order": "desc"}})

    # Handle pagination
    page = int(request.GET.get('page', 1))
    page_size = 96

    # STEP 1: Get featured items separately (only for page 1) using raw OpenSearch client
    featured_results = []
    if page == 1:  # Only fetch featured items for first page
        try:
            client = connections.get_connection()

            # Convert the bool_query to dict properly to preserve all filters
            if hasattr(bool_query, 'to_dict'):
                base_query_dict = bool_query.to_dict()
            else:
                base_query_dict = bool_query

            # Apply the same sorting logic as the main search
            sort_by = request.GET.get('sort_by', 'newlyAdded')
            has_search_terms = bool(query or search_keyword)

            # Determine sort order for featured items
            if sort_by == 'lowToHigh':
                featured_sort = [{"price": {"order": "asc"}}]
            elif sort_by == 'highToLow':
                featured_sort = [{"price": {"order": "desc"}}]
            elif sort_by == 'newlyAdded':
                # Always sort by ID for "newlyAdded", even with curated filters
                featured_sort = [{"id": {"order": "desc"}}]
            elif has_search_terms:
                featured_sort = ["_score"]
            else:
                featured_sort = [{"id": {"order": "desc"}}]  # newlyAdded

            # Create featured query with the same filters as the main search
            featured_query = {
                "query": {
                    "bool": {
                        "must": base_query_dict.get("bool", {}).get("must", []),
                        "filter": base_query_dict.get("bool", {}).get("filter", []) + [
                            {"term": {"featured": True}}  # Add featured filter to existing filters
                        ],
                        "should": base_query_dict.get("bool", {}).get("should", []),
                        "must_not": base_query_dict.get("bool", {}).get("must_not", [])
                    }
                },
                "sort": featured_sort,  # Apply the same sort as main search
                "size": 6  # Limit to 6 featured items
            }

            # Remove empty clauses to keep query clean
            if not featured_query["query"]["bool"]["must"]:
                del featured_query["query"]["bool"]["must"]
            if not featured_query["query"]["bool"]["should"]:
                del featured_query["query"]["bool"]["should"]
            if not featured_query["query"]["bool"]["must_not"]:
                del featured_query["query"]["bool"]["must_not"]

            # Execute raw search
            featured_response = client.search(
                index='core_ebay_items',
                body=featured_query
            )

            featured_hits = featured_response['hits']['hits']

            # Convert featured results to serializable format
            for i, item in enumerate(featured_hits):
                try:
                    source = item['_source']

                    serializable_item = {
                        'featured': True,  # Always true for featured items
                        'item_id': str(source.get('item_id', '')),
                        'categoryId': str(source.get('categoryId', '')),
                        'title': str(source.get('title', '')),
                        'brand': str(source.get('brand', '')),
                        'id': str(source.get('id', '')),
                        'price': float(source.get('price', 0)),
                        'gallery_url': str(source.get('gallery_url', '')),
                        'item_web_url': str(source.get('item_web_url', '')),
                        'color': str(source.get('color', '')),
                        'us_shoe_size': str(source.get('us_shoe_size', '')),
                        'shoe_size_width': str(source.get('shoe_size_width', '')),
                        'bottoms_size': str(source.get('bottoms_size', '')),
                        'chest_size': str(source.get('chest_size', '')),
                        'waist_size': str(source.get('waist_size', '')),
                        'size': str(source.get('size', '')),
                        'bra_size': str(source.get('bra_size', '')),
                        'hat_size': str(source.get('hat_size', '')),
                        'hip_size': str(source.get('hip_size', '')),
                        'inseam': str(source.get('inseam', '')),
                        'shoulder_to_shoulder': str(source.get('shoulder_to_shoulder', '')),
                        'waist_to_hem': str(source.get('waist_to_hem', '')),
                        'shoulder_to_hem': str(source.get('shoulder_to_hem', '')),
                        'ring_size': str(source.get('ring_size', '')),
                        'necklace_length': str(source.get('necklace_length', '')),
                        'item_length': str(source.get('item_length', '')),
                    }
                    featured_results.append(serializable_item)

                except Exception as e:
                    logger.error(f"Error serializing featured item {i}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Featured search error: {e}")

    # STEP 2: Modify main search to exclude featured items
    search = search.filter('term', featured=False)  # Exclude featured items from main results

    # Sorting
    sort_by = request.GET.get('sort_by', 'newlyAdded')
    has_search_terms = bool(query or search_keyword)

    if sort_by == 'lowToHigh':
        featured_sort = [{"price": {"order": "asc"}}]
    elif sort_by == 'highToLow':
        featured_sort = [{"price": {"order": "desc"}}]
    elif sort_by == 'newlyAdded':
        # Always sort by ID for "newlyAdded", even with curated filters
        featured_sort = [{"id": {"order": "desc"}}]
    elif has_search_terms:
        featured_sort = ["_score"]
    else:
        featured_sort = [{"id": {"order": "desc"}}]  # newlyAdded


    # Handle pagination for regular items
    from_ = (page - 1) * page_size
    search = search[from_:from_ + page_size]

    # Execute the search with error handling
    try:
        response = search.execute()
        results = response.hits.hits
        total_results = response.hits.total.value if hasattr(response.hits.total, 'value') else response.hits.total

    except Exception as e:
        logger.error(f"opensearch_results: Search execution error: {e}")
        results = []
        total_results = 0

    # Convert regular results to serializable format
    regular_results = []
    for i, item in enumerate(results):
        try:
            if hasattr(item, '_source'):
                source = item._source
            else:
                source = item['_source']

            if hasattr(source, 'to_dict'):
                source = source.to_dict()

            serializable_item = {
                'featured': False,  # Always false for regular items
                'item_id': str(source.get('item_id', '')),
                'categoryId': str(source.get('categoryId', '')),
                'title': str(source.get('title', '')),
                'brand': str(source.get('brand', '')),
                'id': str(source.get('id', '')),
                'price': float(source.get('price', 0)),
                'gallery_url': str(source.get('gallery_url', '')),
                'item_web_url': str(source.get('item_web_url', '')),
                'color': str(source.get('color', '')),
                'us_shoe_size': str(source.get('us_shoe_size', '')),
                'shoe_size_width': str(source.get('shoe_size_width', '')),
                'bottoms_size': str(source.get('bottoms_size', '')),
                'chest_size': str(source.get('chest_size', '')),
                'waist_size': str(source.get('waist_size', '')),
                'size': str(source.get('size', '')),
                'bra_size': str(source.get('bra_size', '')),
                'hat_size': str(source.get('hat_size', '')),
                'hip_size': str(source.get('hip_size', '')),
                'inseam': str(source.get('inseam', '')),
                'shoulder_to_shoulder': str(source.get('shoulder_to_shoulder', '')),
                'waist_to_hem': str(source.get('waist_to_hem', '')),
                'shoulder_to_hem': str(source.get('shoulder_to_hem', '')),
                'ring_size': str(source.get('ring_size', '')),
                'necklace_length': str(source.get('necklace_length', '')),
                'item_length': str(source.get('item_length', '')),
            }
            regular_results.append(serializable_item)

        except Exception as e:
            logger.error(f"opensearch_results: Error serializing item {i}: {e}")
            continue

    context = {
        'featured_items': featured_results,
        'all_items': regular_results,
        'total_results': total_results,
        'current_page': page,
        'total_pages': (total_results + page_size - 1) // page_size,
    }

    # Return response based on request type
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'featured_items': featured_results,
            'results': regular_results,
            'total_results': total_results,
            'current_page': page,
            'total_pages': (total_results + page_size - 1) // page_size
        })

    logger.debug(f"Featured items count: {len(featured_results)}")
    logger.debug(f"Regular items count: {len(regular_results)}")

    return render(request, 'core/browse.html', context)

def find_item_by_slug(slug):
    """
    Find a specific item by its slug across all your data
    This should search your OpenSearch/database for the item
    """
    # Remove the ID suffix and search by title
    base_slug = slug.replace(r'_\d+$', '')
    title_query = base_slug.replace('_', ' ').title()

    # Search in OpenSearch/database
    # Return the item if found
    pass

@never_cache
def browse_view(request, item_slug=None):
    formatted_time_since_update = calculate_time_since_update() # Call calculate_time_since_update to render formatted time since update
    modified_distinct_colors = normalize_colors() # Call normalize_colors to render available colors
    category_names, all_category_names, unique_top_level_categories, available_sizes, category_display_names, clothing_subgroups, shoe_size_width_mapping = create_categories()

    # Remove empty size category buttons from displayiing on frontend
    available_sizes = {category: sizes for category, sizes in available_sizes.items() if sizes}

    # Apply custom sorting and fraction conversion for size categories
    for category, sizes in available_sizes.items():
        available_sizes[category] = sort_sizes(sizes)

    # Remove empty clothing subgroups from displaying on frontend
    available_category_names = [cat['name'] for cat in category_names if cat['top_level_category'] == 'Clothing']
    filtered_clothing_subgroups = {
        subgroup_name: subgroup_categories
        for subgroup_name, subgroup_categories in clothing_subgroups.items()
        if any(cat_name in available_category_names for cat_name in subgroup_categories)
    }


    context = {
        'distinct_colors': modified_distinct_colors,
        'latest_timestamp': formatted_time_since_update,
        'category_names': category_names,
        'unique_top_level_categories': unique_top_level_categories,
        'available_sizes': available_sizes,
        'category_display_names': category_display_names,
        'top_level_category': unique_top_level_categories,
        'clothing_subgroups': filtered_clothing_subgroups,
        'shoe_size_width_mapping': shoe_size_width_mapping,
        'category_names': category_names,
        'curated_filters': CURATED_FILTERS,
    }

    if item_slug:

        # Remove trailing slash and normalize case
        clean_slug = item_slug.rstrip('/').lower()
        gallery_url_pattern = f'webp_images/{clean_slug}.webp'

        try:
            item = CoreEbayitem.objects.get(gallery_url=gallery_url_pattern)

            context['pdp_item'] = {
                'item_id': item.item_id,
                'title': item.title,
                'gallery_url': item.gallery_url,
                'price': str(item.price) if item.price else None,
                'item_web_url': item.item_web_url,
                # All size fields
                'size': item.size,
                'us_shoe_size': item.us_shoe_size,
                'shoe_size_width': item.shoe_size_width,
                'hat_size': item.hat_size,
                'chest_size': item.chest_size,
                'bra_size': item.bra_size,
                'waist_size': item.waist_size,
                'hip_size': item.hip_size,
                'waist_to_hem': item.waist_to_hem,
                'inseam': item.inseam,
                'shoulder_to_shoulder': item.shoulder_to_shoulder,
                'shoulder_to_hem': item.shoulder_to_hem,
                'women_size': item.women_size,
                'bottoms_size': item.bottoms_size,
                'ring_size': item.ring_size,
                'necklace_length': item.necklace_length,
                'item_length': item.item_length,
                # Add other fields needed for openPDP()
            }
            logger.debug(f"PDP item data: {context['pdp_item']}")


            context['is_pdp_request'] = True
            logger.debug(f"Found PDP item: {item.title}")

        except CoreEbayitem.DoesNotExist:
            context['pdp_item_not_found'] = True
            logger.warning(f"PDP item not found for: {gallery_url_pattern}")

    return render(request, 'core/browse.html', context)
