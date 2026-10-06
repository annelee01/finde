from django.test import SimpleTestCase

from core.size_sorting import extract_size_to_process
from core.tests.utils import requires_implementation


@requires_implementation(extract_size_to_process)
class TestSizeParser(SimpleTestCase):
    """Tests for the `extract_size_to_process` function."""

    def test_valid_bra_sizes(self):
        """Test cases for valid bra sizes."""
        test_cases = [
            ("1218 Front Close Underwire Bra Peach 34B #01218", "34B"),
            ("bra 34B-34C", "34B 34C"),  # Standard range with hyphen
            ("bra 34 B to 34 C", "34B 34C"),  # Range with 'to'
            ("bra 34B 34C", "34B 34C"),  # No range, just a pair
            ("bra 34 A - 34 B", "34A 34B"),  # Simple range
            ('bra 34 B"', "34B"),  # Accidental double quote
            ("bra 34 B'", "34B"),  # Accidental single quote
            ('bra 34B "to" 34C', "34B 34C"),  # Double quotes around "to"
            ("bra 34'B to 34\"C", "34B 34C"),  # Single and double quotes
            ("bra 34\" B and 34' C", "34B 34C"),  # Mixed accidental indicators
            ("bra 34'B-34'C", "34B 34C"),  # Single quotes around range
            ('bra "34A" to "34C"', "34A 34C"),  # Quoted range with 'to'
            ("bra 34\" A - 34' B", "34A 34B"),  # Mixed quotes with range   
        ]
        for size_str, expected_output in test_cases:
            with self.subTest(size_str=size_str):
                result = extract_size_to_process(size_str, "BrandName")  # Provide a brand name
                self.assertIn("bra_size", result, f"'bra_size' not found in result for size_str: {size_str}")
                self.assertEqual(result["bra_size"], expected_output, 
                                 f"Mismatch for size_str: {size_str}. Expected: {expected_output}, Got: {result['bra_size']}")

    def test_invalid_bra_sizes(self):
        """Test cases for invalid bra sizes."""
        test_cases = [
            ("XS", None),
            ("No size", None),
            ("1234", None),
            ("", None),
            ("60s", None),
            ("60's", None),
            ("1920s", None),
            ("1920's", None),
        ]
        for size_str, expected_output in test_cases:
            with self.subTest(size_str=size_str):
                result = extract_size_to_process(size_str, "BrandName")  # Provide a brand name
                if result is None:
                    self.assertIsNone(expected_output, f"Expected None but got result for size_str: {size_str}")
                else:
                    self.assertIn("bra_size", result, f"'bra_size' not found in result for size_str: {size_str}")
                    self.assertEqual(result["bra_size"], expected_output, 
                                     f"Mismatch for size_str: {size_str}. Expected: {expected_output}, Got: {result['bra_size']}")

    def test_edge_cases(self):
        """Edge case tests for bra size parsing."""
        test_cases = [
            ("cup 34 B ", "34B"),  # Space in input should normalize
            (" ", None),  # Empty input should return None
            ("bra 34B-34C", "34B 34C"),  # Hyphenated range normalization
        ]
        for size_str, expected_output in test_cases:
            with self.subTest(size_str=size_str):
                result = extract_size_to_process(size_str, "BrandName")  # Provide a brand name
                if result is None:
                    self.assertIsNone(expected_output, f"Expected None but got result for size_str: {size_str}")
                else:
                    self.assertIn("bra_size", result, f"'bra_size' not found in result for size_str: {size_str}")
                    self.assertEqual(result["bra_size"], expected_output, 
                                     f"Mismatch for size_str: {size_str}. Expected: {expected_output}, Got: {result['bra_size']}")


@requires_implementation(extract_size_to_process)
class TestLingerieSizeExtraction(SimpleTestCase):
    """Tests for lingerie-related size extraction."""

    def test_lingerie_terms_with_sizes(self):
        """Test cases for extracting sizes with lingerie terms."""
        test_cases = [
            ("sz 4 slip 32 bust", {"numeric_plain_size": "4", "chest_size": "32"}),
            ("32-36 waist corset", {"waist_size": "32 33 34 35 36"}),
            ("34C bra", {"bra_size": "34C"}),
            ("32 camisole", {"chest_size": "32"}),
            ("38B bralette", {"bra_size": "38B"}),
            ("32 slip", {"chest_size": "32"}),
            ("32-34 nightgown", {"chest_size": "32 34"}),
            ("2 nightgown", {"numeric_plain_size": "2"}),
            ("hips 36-38 nightgown", {"hip_size": "36 37 38"}),
            ("Slip W 38/16", {"waist_size": "38", "numeric_plain_size": "16"}),
            ("Slip STYLE 2351 Beige Full Slip Slimming Dress Camisole", {"chest_size": ""}),
            ("Top Blouse Women\'s 36\" Bust", {"chest_size": "36", "numeric_plain_size": "", "bra_size": ""}),
            ("Slip Dress 40 Bust ", {"chest_size": "40", "numeric_plain_size": None, "bra_size": None}),
            ("Jacket Size 38", {"chest_size": "", "numeric_plain_size": "38"}),
            # If the numeric slip size is less than 30 (e.g., "size 8", "size 10"), treat it as a dress size (size).
            ("Lingerie Slip Dress Size 8", {"numeric_plain_size": "8", "chest_size": "", "bra_size": ""}),
            # If the numeric slip size is between 30 and 46 (e.g., "size 34", "size 36"), treat it as a bust size (bra_size).
            ("Lingerie Slip Dress Size 32", {"numeric_plain_size": "", "chest_size": "32", "bra_size": ""}),
            ("90's Vanity Fair Camisole Beige Nylon Silky Lace Women's 36", {"chest_size": "36", "bra_size": ""}),
            ("Bra Top Stretch Satin Full Slip girdle 40 42 Smoothing Dress UW 1X 14", {"chest_size": "40 42", "numeric_size": "14 1x", "numeric_plain_size": "14"}),
            ("Slip 38 White with 6 Inch Lace Trim", {"chest_size": "38", "numeric_plain_size": "None", "numeric_size": ""}),
            ("Sweater Gray Short Sleeves Womens Sz S 50's", {"numeric_size": "", "standalone_size": "S", "numeric_plain_size": None,}),
            ("Silk Shirt & Pants Y2K Set Combo Sz 42", {"numeric_plain_size": "42",}),
            ("Suit B 36\'/ W 29\"", {"waist_size": "29", "chest_size": "36", "numeric_plain_size": ""}),
            ("Vintage 05C CC Logo Knit Top #36 Sweater Camisole", {"numeric_plain_size": "", "numeric_size": ""}), # '05c' or any preceeding '0' number is invalid ('00 is still valid')
            ("Vintage 00 CC Logo Knit Top #36 Sweater Camisole", {"numeric_size": "00"}), # '05c' or any preceeding '0' number is invalid ('00 is still valid')
            ("Shoes Vintage Womens 10 AA", {"us_shoe_size": "10"}), # Converts '10 AA' shoe size to '10s'
            ("Leather Heels Narrow Sz 6.5 AAA", {"us_shoe_size": "6.5"}), # Converts '6.5 AAA' shoe size to '6.5XS'
            ("Heels Sz 8AAAA", {"us_shoe_size": "8"}), # Converts '8AAAA' shoe size to '8XS'
            ("Heels Women's 5 1/2 D", {"us_shoe_size": "5.5"}), 
            ("Heel Pumps 40 B italy", {"us_shoe_size": "10", "bra_size": None,}), 
            ("FERRAGAMO- 1990s Black Satin Bow Pumps, Size 6 1/2 B", {"us_shoe_size": "6.5", "bra_size": None,}), 
            ]
        for title, expected_output in test_cases:
            with self.subTest(title=title):
                
                result = extract_size_to_process(title, "BrandName")  # Provide a brand name
                
                for key, value in expected_output.items():
                      # Check if the result is None when no sizes are found
                    if result is None:
                        self.assertIsNone(result, f"Expected None, but got {result}")
                    else:
                        self.assertIn(key, result, f"'{key}' not found in result for title: {title}")
                        self.assertEqual(str(result[key]), str(value),
                                        f"Mismatch for title: {title}. Expected: {value}, Got: {result[key]}")


@requires_implementation(extract_size_to_process)
class TestShoeSizeConversion(SimpleTestCase):
    """Test case for shoe size conversion."""

    def test_shoe_size_conversion(self):
        """Test case for extracting and converting shoe sizes."""
        
        test_cases = [
            ("Heel Pumps 5 UK", {
                'foot_length_in': 9.7,
                'europe_shoe_size': 38,
                'uk_shoe_size': 5,
                'france_shoe_size': 39,
                'us_shoe_size': 8,
                'japan_shoe_size': 25,
                'korea_china_shoe_size': 250
            }),
            ("Heels Sz 38 Tom Ford", {
                'foot_length_in': 9.7,
                'europe_shoe_size': 38,
                'uk_shoe_size': 5,
                'france_shoe_size': 39,
                'us_shoe_size': 8,
                'japan_shoe_size': 25,
                'korea_china_shoe_size': 250
            }),
            ("Dr martens shoes Size EU38/UK5/US7", { # NOTE these title values don't align with my shoe conversion table, so 'US' size '7' gets prioritized
                'foot_length_in': 9.5,
                'europe_shoe_size': 37,
                'uk_shoe_size': 4,
                'france_shoe_size': 38,
                'us_shoe_size': 7,
                'japan_shoe_size': 24,
                'korea_china_shoe_size': 240,
            }),
            ("60s Vintage Aldrovandi Leather Pumps, Black, Italy - 40 (8.5 - 9)", {
                'foot_length_in': 10.2,
                'europe_shoe_size': 40,
                'uk_shoe_size': 7,
                'france_shoe_size': 41,
                'us_shoe_size': 10,
                'japan_shoe_size': 27,
                'korea_china_shoe_size': 270,
            }),
            ("PRADA MILANO SILK SHOES - SIZE 39", {
                'foot_length_in': 10,
                'europe_shoe_size': 39,
                'uk_shoe_size': 6,
                'france_shoe_size': 40,
                'us_shoe_size': 9,
                'japan_shoe_size': 26,
                'korea_china_shoe_size': 260,
            }),
            ("Gucci heels SIZE 9", { # make sure '9' is assigned to US size, despite IT region detected by 'Gucci' keyword
                'foot_length_in': 10,
                'europe_shoe_size': 39,
                'uk_shoe_size': 6,
                'france_shoe_size': 40,
                'us_shoe_size': 9,
                'japan_shoe_size': 26,
                'korea_china_shoe_size': 260,
            }),
            ("Vintage Prada Suede Loafer Kitten Heel Pumps Beige Square Toe w/Bow Size 37 US 7", { # make sure parsing '/' from 'w/' in title doesn't lead to errors
                'foot_length_in': 9.5,
                'europe_shoe_size': 37,
                'uk_shoe_size': 4,
                'france_shoe_size': 38,
                'us_shoe_size': 7,
                'japan_shoe_size': 24,
                'korea_china_shoe_size': 240,
            }),
            ("SALVATORE FERRAGAMO SLINGBACK PUMPS SHOES US 6.5 EU 37", { # make sure parsing numeral size + region pairings corretly 
                'foot_length_in': 9.3,
                'europe_shoe_size': 36.5,
                'uk_shoe_size': 3.5,
                'france_shoe_size': 37.5,
                'us_shoe_size': 6.5,
                'japan_shoe_size': 23.5,
                'korea_china_shoe_size': 235,
            }),
            ("5½ B (EU36) ESCADA ALL LEATHER SLINGBACK Heels", { # make sure parsing numeral size + region pairings corretly 
                'foot_length_in': 9.1,
                'europe_shoe_size': 35.5,
                'uk_shoe_size': 2.5,
                'france_shoe_size': 36.5,
                'us_shoe_size': 5.5,
                'japan_shoe_size': 22.5,
                'korea_china_shoe_size': 225,
            }),
            ("Unknown Brand Vintage Size 36 Shoes", { # make sure parsing numeral size + region pairings corretly 
                'foot_length_in': 9.2,
                'europe_shoe_size': 36,
                'uk_shoe_size': 3,
                'france_shoe_size': 37,
                'us_shoe_size': 6,
                'japan_shoe_size': 23,
                'korea_china_shoe_size': 230,
            }),
            ("high heels, brown, never worn, in box Size 6.5 $40 OBO", { # ignore $40 
                'foot_length_in': 9.3,
                'europe_shoe_size': 36.5,
                'uk_shoe_size': 3.5,
                'france_shoe_size': 37.5,
                'us_shoe_size': 6.5,
                'japan_shoe_size': 23.5,
                'korea_china_shoe_size': 235,
            }),
            ("Miss Maude Paris VTG Women's 40s 50s Solid Black Heels Pumps Sz 37 1/2 6.5 - 7 ?", { # ignore $40 
                'foot_length_in': 9.3,
                'europe_shoe_size': 36.5,
                'uk_shoe_size': 3.5,
                'france_shoe_size': 37.5,
                'us_shoe_size': 6.5,
                'japan_shoe_size': 23.5,
                'korea_china_shoe_size': 235,
            }),
            ("Women\'s Black Suede Sandal Sz 9N 34-331", { # 9N should be able to convert the rest of the shoe size info region conversions
                'foot_length_in': 10,
                'europe_shoe_size': 39,
                'uk_shoe_size': 6,
                'france_shoe_size': 40,
                'us_shoe_size': 9,
                'japan_shoe_size': 26,
                'korea_china_shoe_size': 260,
            }),
            ("PRADA VINTAGE PEEP TOE 3 1/2\" VERO CUOIO ITALY PATENT LEATHER STILETTO EUO 35.5", { # heel height 3 1/2 should fail detect, then continue to loop through matches to detect EU 35.5, 
                'foot_length_in': 9.1,
                'europe_shoe_size': 35.5,
                'uk_shoe_size': 2.5,
                'france_shoe_size': 36.5,
                'us_shoe_size': 5.5,
                'japan_shoe_size': 22.5,
                'korea_china_shoe_size': 225,
            }),
        ]

        for title, expected_output in test_cases:
            with self.subTest(title=title):
                # Extract shoe size
                extracted_result = extract_size_to_process(title, "BrandName")  # Adjust brand name as necessary

                # Validate results directly
                for key, value in expected_output.items():
                    self.assertIn(key, extracted_result, f"'{key}' not found in result for title: {title}")
                    self.assertEqual(
                        extracted_result[key],
                        value,
                        f"Mismatch for title: {title}. Expected: {value}, Got: {extracted_result[key]}"
                    )
