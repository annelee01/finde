from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import Category, MarketplaceItem

# The production taxonomy isn't published; a small sample exercises the same shapes
SAMPLE_TAXONOMY = {
    'clothing': {
        'tops': {'blouses': ['silk_blouse', 'peasant_blouse'], 'tees': ['graphic_tee']},
    },
    'shoes': {'heels': ['pumps', 'slingbacks']},
    'accessories': {
        'jewelry': {'necklaces': ['pendant']},
        'belts': ['leather_belt'],
    },
}


@patch('core.views.marketplace.FASHION_TAXONOMY', SAMPLE_TAXONOMY)
class CategoryTaxonomyApiTests(TestCase):
    def test_breadcrumb_formats_each_level(self):
        response = self.client.get(reverse('core:category_breadcrumb'), {'path': 'clothing.tops.blouses'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['breadcrumb'], [
            {'name': 'Clothing', 'path': 'clothing'},
            {'name': 'Tops', 'path': 'clothing.tops'},
            {'name': 'Blouses', 'path': 'clothing.tops.blouses'},
        ])

    def test_search_requires_two_characters(self):
        response = self.client.get(reverse('core:search_categories'), {'q': 'a'})
        self.assertEqual(response.json()['results'], [])

    def test_search_returns_matching_categories(self):
        response = self.client.get(reverse('core:search_categories'), {'q': 'blouse'})
        names = [result['name'].lower() for result in response.json()['results']]
        self.assertTrue(names)
        self.assertTrue(all('blouse' in name for name in names))

    def test_category_tree_has_top_level_groups(self):
        response = self.client.get(reverse('core:category_tree'))
        self.assertTrue(response.json()['success'])
        tree = {node['id']: node for node in response.json()['categories']}
        self.assertEqual(set(tree), {'clothing', 'shoes', 'accessories', 'jewelry'})

        blouses = tree['clothing']['children'][0]['children'][0]
        self.assertEqual(blouses['path'], 'clothing.tops.blouses')
        self.assertEqual([c['name'] for c in blouses['children']], ['Silk Blouse', 'Peasant Blouse'])

        # Jewelry is promoted to its own top-level group; other accessories stay nested
        self.assertEqual([c['id'] for c in tree['accessories']['children']], ['accessories.belts'])


class MarketplaceItemListApiTests(TestCase):
    def setUp(self):
        seller = User.objects.create_user('seller')
        category = Category.objects.create(name='Coats', slug='coats')
        common = {'seller': seller, 'category': category, 'is_active': True}
        MarketplaceItem.objects.create(title='Camel wool coat', brand='Max Mara', price=320, **common)
        MarketplaceItem.objects.create(title='Black trench', brand='Burberry', price=150, **common)

    def test_search_filters_by_title_and_brand(self):
        url = reverse('core:api_list_items')
        titles = [item['title'] for item in self.client.get(url, {'search': 'wool'}).json()['results']]
        self.assertEqual(titles, ['Camel wool coat'])

        titles = [item['title'] for item in self.client.get(url, {'search': 'burberry'}).json()['results']]
        self.assertEqual(titles, ['Black trench'])

    def test_price_range_filter(self):
        response = self.client.get(reverse('core:api_list_items'), {'max_price': 200})
        self.assertEqual([item['title'] for item in response.json()['results']], ['Black trench'])
