import re
from .maps_and_terms import REGEX_PATTERNS, SHOE_WIDTH_MAP
from fractions import Fraction
BRAND_REGION_MAP = {}
REGION_FULL_NAME_KEY_MAP = {}
REGION_KEY_MAP = {}
final_shoe_size = None
shoe_numeric_part = None
shoe_size_conversion_table = [{'foot_length_in': 8.7, 'europe_shoe_size': 34, 'uk_shoe_size': 1, 'france_shoe_size': 35, 'us_shoe_size': 4, 'japan_shoe_size': 21, 'korea_china_shoe_size': 210}, {'foot_length_in': 8.8, 'europe_shoe_size': 34.5, 'uk_shoe_size': 1.5, 'france_shoe_size': 35.5, 'us_shoe_size': 4.5, 'japan_shoe_size': 21.5, 'korea_china_shoe_size': 215}, {'foot_length_in': 8.9, 'europe_shoe_size': 35, 'uk_shoe_size': 2, 'france_shoe_size': 36, 'us_shoe_size': 5, 'japan_shoe_size': 22, 'korea_china_shoe_size': 220}, {'foot_length_in': 9.1, 'europe_shoe_size': 35.5, 'uk_shoe_size': 2.5, 'france_shoe_size': 36.5, 'us_shoe_size': 5.5, 'japan_shoe_size': 22.5, 'korea_china_shoe_size': 225}, {'foot_length_in': 9.2, 'europe_shoe_size': 36, 'uk_shoe_size': 3, 'france_shoe_size': 37, 'us_shoe_size': 6, 'japan_shoe_size': 23, 'korea_china_shoe_size': 230}, {'foot_length_in': 9.3, 'europe_shoe_size': 36.5, 'uk_shoe_size': 3.5, 'france_shoe_size': 37.5, 'us_shoe_size': 6.5, 'japan_shoe_size': 23.5, 'korea_china_shoe_size': 235}, {'foot_length_in': 9.5, 'europe_shoe_size': 37, 'uk_shoe_size': 4, 'france_shoe_size': 38, 'us_shoe_size': 7, 'japan_shoe_size': 24, 'korea_china_shoe_size': 240}, {'foot_length_in': 9.6, 'europe_shoe_size': 37.5, 'uk_shoe_size': 4.5, 'france_shoe_size': 38.5, 'us_shoe_size': 7.5, 'japan_shoe_size': 24.5, 'korea_china_shoe_size': 245}, {'foot_length_in': 9.7, 'europe_shoe_size': 38, 'uk_shoe_size': 5, 'france_shoe_size': 39, 'us_shoe_size': 8, 'japan_shoe_size': 25, 'korea_china_shoe_size': 250}, {'foot_length_in': 9.8, 'europe_shoe_size': 38.5, 'uk_shoe_size': 5.5, 'france_shoe_size': 39.5, 'us_shoe_size': 8.5, 'japan_shoe_size': 25.5, 'korea_china_shoe_size': 255}, {'foot_length_in': 10, 'europe_shoe_size': 39, 'uk_shoe_size': 6, 'france_shoe_size': 40, 'us_shoe_size': 9, 'japan_shoe_size': 26, 'korea_china_shoe_size': 260}, {'foot_length_in': 10.1, 'europe_shoe_size': 39.5, 'uk_shoe_size': 6.5, 'france_shoe_size': 40.5, 'us_shoe_size': 9.5, 'japan_shoe_size': 26.5, 'korea_china_shoe_size': 265}, {'foot_length_in': 10.2, 'europe_shoe_size': 40, 'uk_shoe_size': 7, 'france_shoe_size': 41, 'us_shoe_size': 10, 'japan_shoe_size': 27, 'korea_china_shoe_size': 270}, {'foot_length_in': 10.3, 'europe_shoe_size': 40.5, 'uk_shoe_size': 7.5, 'france_shoe_size': 41.5, 'us_shoe_size': 10.5, 'japan_shoe_size': 27.5, 'korea_china_shoe_size': 275}, {'foot_length_in': 10.5, 'europe_shoe_size': 41, 'uk_shoe_size': 8, 'france_shoe_size': 42, 'us_shoe_size': 11, 'japan_shoe_size': 28, 'korea_china_shoe_size': 280}, {'foot_length_in': 10.6, 'europe_shoe_size': 41.5, 'uk_shoe_size': 8.5, 'france_shoe_size': 42.5, 'us_shoe_size': 11.5, 'japan_shoe_size': 28.5, 'korea_china_shoe_size': 285}, {'foot_length_in': 10.7, 'europe_shoe_size': 42, 'uk_shoe_size': 9, 'france_shoe_size': 43, 'us_shoe_size': 12, 'japan_shoe_size': 29, 'korea_china_shoe_size': 290}]

def convert_shoe_size_by_region(shoe_numeric_part, region):
    """Proprietary implementation omitted in this public repository."""
    pass

def split_alpha_numeric_parts(parts):
    """
        Split each size part into alphabetic and numeric components.

Proprietary implementation omitted in this public repository."""
    pass

def check_shoe_size_matches(value):
    """Proprietary implementation omitted in this public repository."""
    pass
