from django.template import Context, Template
from django.test import SimpleTestCase

from core.templatetags.custom_tags import decimal_to_fraction


class DecimalToFractionTests(SimpleTestCase):
    def test_common_fractions_render_as_superscript(self):
        cases = {
            '20.5': '20 <sup>1/2</sup>',
            '6.25': '6 <sup>1/4</sup>',
            '6.375': '6 <sup>3/8</sup>',
            '30.75': '30 <sup>3/4</sup>',
            '7.875': '7 <sup>7/8</sup>',
        }
        for size, expected in cases.items():
            with self.subTest(size=size):
                self.assertEqual(decimal_to_fraction(size), expected)

    def test_whole_and_uncommon_values_are_unchanged(self):
        self.assertEqual(decimal_to_fraction('28'), '28')
        self.assertEqual(decimal_to_fraction('30.1'), '30.1')

    def test_inch_marks_are_stripped(self):
        self.assertEqual(decimal_to_fraction('20.5"'), '20 <sup>1/2</sup>')

    def test_non_numeric_sizes_are_escaped(self):
        self.assertEqual(decimal_to_fraction('M'), 'M')
        self.assertEqual(decimal_to_fraction('<b>XL</b>'), '&lt;b&gt;XL&lt;/b&gt;')

    def test_renders_without_safe_filter(self):
        template = Template('{% load custom_tags %}{{ size|decimal_to_fraction }}')
        self.assertEqual(template.render(Context({'size': '20.5'})), '20 <sup>1/2</sup>')
        self.assertEqual(
            template.render(Context({'size': '<script>x</script>'})),
            '&lt;script&gt;x&lt;/script&gt;',
        )
