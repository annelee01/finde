from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class PageRenderTests(TestCase):
    def test_home_page_embeds_curated_filters_as_json(self):
        response = self.client.get(reverse('core:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<script id="curated-filters-data" type="application/json">')

    @patch('core.views.marketplace.fashion_taxonomy', SimpleNamespace(
        # The production taxonomy isn't published; sample data with a script-breaking value
        detection_mappings={'dress': '</script><b>dress</b>'},
        top_level_categories={'clothing': {}},
    ))
    def test_create_listing_page_embeds_fashion_data_as_json(self):
        self.client.force_login(User.objects.create_user('seller'))
        response = self.client.get(reverse('core:create_listing'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<script id="fashion-data" type="application/json">')
        self.assertNotContains(response, '</script><b>dress</b>')

    def test_static_pages_render(self):
        for name in ['core:about', 'core:tos', 'core:contact', 'core:newsletter']:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
