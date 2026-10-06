from unittest.mock import patch

from django.test import SimpleTestCase

from core.size_sorting import extract_size_to_process
from core.tests.utils import requires_implementation


@requires_implementation(extract_size_to_process)
class TestExtractSizeFromTitle(SimpleTestCase):

    @patch('core.size_sorting.normalize_pants_size')  
    def test_ignore_quantity_3_sweaters(self, mock_normalize_pants_size):
        # Test case to ensure quantity "3" in "3 sweaters" is ignored
        title = "Wholesale 3 Sweaters Pink Knit Designer"

        # Configure the mock normalization function
        mock_normalize_pants_size.side_effect = lambda value: value.strip()

        # Call the function with the test case
        brand = "SampleBrand"
        size_info = extract_size_to_process(title, brand)

        # Handle case where function returns None
        if size_info is None:
            return  # Test passes - no sizes should be extracted

        # If size_info is returned, ensure 3 is not in any field
        self.assertNotEqual(size_info.get("size"), "3", 
                        f"Should not assign 3 as size for quantity pattern: {title}")
        self.assertNotEqual(size_info.get("numeric_size"), "3", 
                        f"Should not assign 3 to numeric_size for quantity pattern: {title}")
        self.assertNotEqual(size_info.get("chest_size"), "3", 
                        f"Should not assign 3 to chest_size for quantity pattern: {title}")

        # Debugging output
        
        # Additional check - ensure 3 doesn't appear in any field
        for key, value in size_info.items():
            if value and "3" in str(value):
                self.fail(f"Found '3' in field '{key}' with value '{value}' - should be ignored as quantity")
                

    @patch('core.size_sorting.normalize_pants_size')  # Mock the normalization function
    def test_dress_46_assigned_correctly_not_chest(self, mock_normalize_pants_size):
        # Test case to ensure 46 and XL are assigned correctly, not to chest_size
        title = "Vtg Roberto Cavalli Black Floral Print Corset Dress 46 XL"

        # Configure the mock normalization function
        mock_normalize_pants_size.side_effect = lambda value: value.strip()

        # Call the function with the test case
        brand = "Roberto Cavalli"
        size_info = extract_size_to_process(title, brand)

        # Assertions
        self.assertEqual(size_info.get("numeric_size"), "46", 
                        f"Failed to assign 46 to numeric_size for title: {title}")
        self.assertEqual(size_info.get("standalone_size"), "XL", 
                        f"Failed to assign XL to standalone_size for title: {title}")
        
        # Main assertion: chest_size should be empty
        self.assertEqual(size_info.get("chest_size"), "", 
                        f"46 should not be assigned to chest_size for European dress size: {title}")

        # Debugging output

    @patch('core.size_sorting.normalize_pants_size')  # Mock the normalization function
    def test_waist_and_inseam_extraction(self, mock_normalize_pants_size):
        # Test cases with titles and expected waist/inseam sizes
        test_cases_x_format = [
            ("size 28x30", '28', '30'),  # Mixed format
            ("29W x 30L", '29', '30'),  # With W and L
            ("30x32 pants", '30', '32'),  # Standard format with category
            ("30x32 pants", '30', '32'),  # Standard format with category
            ("jeans 30x32", '30', '32'),  # Basic format
            ("pant size 34 x 36", '34', '36'),  # Different phrasing
            ("36W-34L", '36', '34'),  # Hyphen separator
            ("jeans Size: 33x31", '33', '31'),  # Colon separator
            ("Sz L 30/32 Waist Mid Length Slip", '30 32', None)  # Double waist size without inseam

        ]

        test_cases_other_formats = [
            ("waist 32 inseam 34", '32', '34'),  # Explicit labels
            ("jeans Waist 25 Length 30", '25', '30'),  # Explicit description
            ("30 waist 32 inseam", '30', '32'),  # Units swapped
            ("skirt W30 L31", '30', '31'), 
        ]

        test_cases_units = [
            ("waist 32 inches inseam 34 inches", '32', '34'),  # Full word "inches"
            ("waist 32in inseam 34in", '32', '34'),  # Abbreviated unit "in"
            ('waist 32" inseam 34"', '32', '34'),  # Double quotes for inches
            ("waist 32 in. inseam 34 in.", '32', '34'),  # Period after unit
            ("jeans 32\"x34\"", '32', '34'),  # Inches in x format with quotes
            ("23 1/2\" Waist", '23.5', None),  # Fraction with no inseam
        ]

        # New test case for "Jeans Size 27/4"
        test_case_jeans_size = [
            ("Jeans USA 2/26", '26', '2'), # Expected waist_size and numeric_size
            ("Jeans Size 27/4", '27', '4')  # Expected waist_size and numeric_size
        ]

        # Configure the mock to return the waist/inseam values correctly
        def normalize_side_effect(value):
            # Handle different value formats as needed
            if 'W' in value or 'L' in value:  # For 'W x L' or 'W-L' format
                return value.rstrip('WL').strip()
            return value.strip()  # Return as is if no 'W' or 'L'

        mock_normalize_pants_size.side_effect = normalize_side_effect

        # Test the 'x' format test cases
        for title, expected_waist, expected_inseam in test_cases_x_format:
            with self.subTest(title=title):
                # Provide a fixed brand for testing (you can replace this with dynamic brand extraction if necessary)
                brand = "SampleBrand"  # Use a mock or sample brand name here

                # Call the extraction function with both title and brand
                size_info = extract_size_to_process(title, brand)

                # Assertions for waist and inseam values (expecting strings without 'W' or 'L' suffixes)
                self.assertEqual(size_info.get("waist_size"), expected_waist, f"Failed for title: {title}")
                self.assertEqual(size_info.get("inseam"), expected_inseam, f"Failed for title: {title}")

                # Debugging: Check size extraction result

        # Test the other format test cases
        for title, expected_waist, expected_inseam in test_cases_other_formats:
            with self.subTest(title=title):
                # Provide a fixed brand for testing
                brand = "SampleBrand"

                # Call the extraction function with both title and brand
                size_info = extract_size_to_process(title, brand)

                # Assertions for waist and inseam values
                self.assertEqual(size_info.get("waist_size"), expected_waist, f"Failed for title: {title}")
                self.assertEqual(size_info.get("inseam"), expected_inseam, f"Failed for title: {title}")

                # Debugging: Check size extraction result

        # Test the unit variations test cases
        for title, expected_waist, expected_inseam in test_cases_units:
            with self.subTest(title=title):
                # Provide a fixed brand for testing
                brand = "SampleBrand"

                # Call the extraction function with both title and brand
                size_info = extract_size_to_process(title, brand)

                # Assertions for waist and inseam values
                self.assertEqual(size_info.get("waist_size"), expected_waist, f"Failed for title: {title}")
                self.assertEqual(size_info.get("inseam"), expected_inseam, f"Failed for title: {title}")

                # Debugging: Check size extraction result
                
        # Test the new "Jeans Size 27/4" case
        for title, expected_waist, expected_bottoms_size in test_case_jeans_size:
            with self.subTest(title=title):
                # Provide a fixed brand for testing
                brand = "SampleBrand"  # Use a mock or sample brand name here

                # Convert expected_bottoms_size to integer if it's not None
                expected_bottoms_size = int(expected_bottoms_size) if expected_bottoms_size is not None else None

                # Call the extraction function with both title and brand
                size_info = extract_size_to_process(title, brand)

                # Assertions for waist size and numeric size
                self.assertEqual(size_info.get("waist_size"), expected_waist, f"Failed for title: {title}")
                self.assertEqual(size_info.get("bottoms_size"), expected_bottoms_size, f"Failed for title: {title}")

                # Debugging: Check size extraction result

    @patch('core.size_sorting.normalize_pants_size')  # Mock the normalization function
    def test_size_extraction_ignoring_periods_and_bottoms_size(self, mock_normalize_pants_size):
        # Test case for title with "S.M.H." and "size 16" for pants
        test_case = ("S.M.H. Vintage Suede Leather and Crocheted Patchwork Pants Size 16 Gold Retro", 
             {"bottoms_size": "16"})  # Expected result as a str

        title, expected_output = test_case

        # Configure the mock normalization function
        mock_normalize_pants_size.side_effect = lambda value: value.strip()

        # Call the function with the test case
        brand = "SampleBrand"  # Provide a sample brand
        size_info = extract_size_to_process(title, brand)

        # Assertions
        self.assertEqual(size_info.get("bottoms_size"), expected_output.get("bottoms_size"), f"Failed for title: {title}")
        self.assertNotIn("S", size_info.values(), f"Incorrectly extracted 'S' as a size for title: {title}")

        # Debugging output


    @patch('core.size_sorting.normalize_pants_size')  # Mock the normalization function
    def test_specific_title_extraction(self, mock_normalize_pants_size):
        # Test case for the given title
        test_case = (
            "Levi's 529 Womens 6M. 9\" Rise 28x32\" 1990's Straight Leg",
            {"bottoms_size": "6 M", "waist_size": "28", "inseam": "32", "numeric_plain_size": ""}
        )

        title, expected_output = test_case

        # Configure the mock normalization function
        mock_normalize_pants_size.side_effect = lambda value: value.strip()

        # Call the function with the test case
        brand = "Levi's"  # Use the brand extracted or specified in the title
        size_info = extract_size_to_process(title, brand)

        # Assertions
        self.assertEqual(size_info.get("bottoms_size"), expected_output.get("bottoms_size"), f"Failed for title: {title}")
        self.assertEqual(size_info.get("waist_size"), expected_output.get("waist_size"), f"Failed for title: {title}")
        self.assertEqual(size_info.get("inseam"), expected_output.get("inseam"), f"Failed for title: {title}")
        self.assertEqual(size_info.get("numeric_plain_size"), expected_output.get("numeric_plain_size"), f"Failed for title: {title}")


        # Debugging output


    @patch('core.size_sorting.normalize_pants_size')  # Mock the normalization function
    def test_waist_and_inseam_extraction(self, mock_normalize_pants_size):
        # Existing test cases...

        # New test case for "Denim Jeans Size 34"
        test_case_denim_jeans = [
            ("Denim Jeans Size 34", '34', '')  # Expected waist_size is 34, and bottoms_size is empty
        ]

        # Test the new "Denim Jeans Size 34" case
        for title, expected_waist, expected_bottoms_size in test_case_denim_jeans:
            with self.subTest(title=title):
                # Provide a fixed brand for testing
                brand = "SampleBrand"  # Use a mock or sample brand name here

                # Call the extraction function with both title and brand
                size_info = extract_size_to_process(title, brand)

                # Assertions for waist size and bottoms size (expecting an empty string for bottoms_size)
                self.assertEqual(size_info.get("waist_size"), expected_waist, f"Failed for title: {title}")
                self.assertEqual(size_info.get("bottoms_size"), expected_bottoms_size, f"Failed for title: {title}")

                # Debugging: Check size extraction result
                
    @patch('core.size_sorting.normalize_pants_size')  # Mock the normalization function
    def test_specific_title_with_range(self, mock_normalize_pants_size):
        # Test case for the specific title "pleated knee length w10.5-13"
        test_case = (
            "pleated knee length w10.5-13",
            {"waist_size": "21 22 23 24 25 26", "numeric_plain_size": ""}
        )

        title, expected_output = test_case

        # Configure the mock normalization function
        mock_normalize_pants_size.side_effect = lambda value: value.strip()

        # Call the function with the test case
        brand = "SampleBrand"  # Provide a sample brand
        size_info = extract_size_to_process(title, brand)

        # Assertions
        self.assertEqual(size_info.get("numeric_plain_size"), expected_output.get("numeric_plain_size"), f"Failed for title: {title}")
        self.assertEqual(size_info.get("waist_size"), expected_output.get("waist_size"), f"Failed for waist size for title: {title}")

        # Debugging output
