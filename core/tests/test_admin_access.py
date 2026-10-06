import json

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import CoreEbayitem

ADMIN_ONLY_POSTS = [
    ('core:delete_items', {'item_ids': []}),
    ('core:save_items', {}),
    ('core:update_category', {'itemId': '1', 'categoryId': '2'}),
]


def make_item(item_id, **fields):
    defaults = {
        'title': 'Vintage item', 'price': 50, 'gallery_url': f'webp_images/{item_id}.webp',
        'item_web_url': 'https://www.ebay.com/itm/1', 'availability': 'IN_STOCK', 'categoryId': '1',
    }
    return CoreEbayitem.objects.create(item_id=item_id, **{**defaults, **fields})


ADMIN_ONLY_GETS = [
    'core:update_availability',
    'core:get_ended_items',
    'core:manual_relist',
    'search_results',
]


@override_settings(ADMIN_USERNAME='site-admin')
class AdminOnlyViewTests(TestCase):
    """Catalog-management endpoints must be limited to the admin account."""

    def setUp(self):
        self.shopper = User.objects.create_user('shopper', password='pw')
        self.admin = User.objects.create_user('site-admin', password='pw')

    def test_anonymous_users_are_sent_to_login(self):
        for name, payload in ADMIN_ONLY_POSTS:
            with self.subTest(view=name):
                response = self.client.post(reverse(name), json.dumps(payload), content_type='application/json')
                self.assertEqual(response.status_code, 302)
                self.assertIn('/account/login/', response['Location'])
        for name in ADMIN_ONLY_GETS:
            with self.subTest(view=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 302)

    def test_regular_users_are_forbidden(self):
        self.client.force_login(self.shopper)
        for name, payload in ADMIN_ONLY_POSTS:
            with self.subTest(view=name):
                response = self.client.post(reverse(name), json.dumps(payload), content_type='application/json')
                self.assertEqual(response.status_code, 403)
        for name in ADMIN_ONLY_GETS:
            with self.subTest(view=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 403)

    def test_regular_users_cannot_delete_items(self):
        item = make_item('v1|123|0', title='Silk blouse')
        self.client.force_login(self.shopper)

        self.client.post(
            reverse('core:delete_items'),
            json.dumps({'item_ids': [item.item_id]}),
            content_type='application/json',
        )

        self.assertTrue(CoreEbayitem.objects.filter(pk=item.pk).exists())

    def test_admin_can_update_item_category(self):
        item = make_item('v1|456|0', title='Wool coat')
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('core:update_category'),
            json.dumps({'itemId': item.item_id, 'categoryId': '63862', 'featured': True}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.categoryId, '63862')
        self.assertTrue(item.featured)

    def test_delete_items_requires_post(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('core:delete_items')).status_code, 405)


class UploadEndpointTests(TestCase):
    def test_upload_endpoints_reject_get(self):
        for name in ['core:upload_temp_image', 'core:clear_listing_session']:
            with self.subTest(view=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 405)

    def test_upload_endpoints_enforce_csrf(self):
        client = self.client_class(enforce_csrf_checks=True)
        for name in ['core:upload_temp_image', 'core:clear_listing_session']:
            with self.subTest(view=name):
                self.assertEqual(client.post(reverse(name)).status_code, 403)
