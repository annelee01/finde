import importlib

from django.test import SimpleTestCase

from core.size_sorting import extract_size_from_aspect
from core.tests.utils import requires_implementation


@requires_implementation(extract_size_from_aspect)
class TestExtractSizeFromAspect(SimpleTestCase):

    def setUp(self):
        """
        Force isolation by reloading the module before each test to reset shared state.
        """
        global extract_size_from_aspect
        size_sorting = importlib.import_module("core.size_sorting")
        importlib.reload(size_sorting)
        extract_size_from_aspect = size_sorting.extract_size_from_aspect

    def test_word_based_size_range(self):
        result = extract_size_from_aspect("US Shoe Size (Women's)", "5 1/2 W")

        # Expected return format: (True, (dict,))
        expected = (True, ({
            'foot_length_in': 9.1, 
            'europe_shoe_size': 35.5, 
            'uk_shoe_size': 2.5, 
            'france_shoe_size': 36.5, 
            'us_shoe_size': 5.5, 
            'japan_shoe_size': 22.5, 
            'korea_china_shoe_size': 225, 
            'shoe_size_width': 'W'
        },))
