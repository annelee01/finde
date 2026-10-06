from django.contrib.auth.models import User
from django.test import TestCase

from core.forms import SignupForm
from core.utils import make_username_unique


def signup_data(email, password='Password@123', confirm=None):
    return {
        'first_name': 'Test',
        'email': email,
        'password1': password,
        'password2': confirm if confirm is not None else password,
    }


class UniqueUsernameTests(TestCase):
    def test_returns_prefix_when_unused(self):
        self.assertEqual(make_username_unique('flowerpower'), 'flowerpower')

    def test_appends_counter_starting_at_one(self):
        User.objects.create_user('flowerpower')
        self.assertEqual(make_username_unique('flowerpower'), 'flowerpower1')

        User.objects.create_user('flowerpower1')
        self.assertEqual(make_username_unique('flowerpower'), 'flowerpower2')


class SignupFormTests(TestCase):
    def test_username_is_generated_from_email_prefix(self):
        form = SignupForm(data=signup_data('flowerpower@example.com'))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['username'], 'flowerpower')

    def test_generated_username_avoids_existing_users(self):
        User.objects.create_user('flowerpower', email='flowerpower@example.com')
        form = SignupForm(data=signup_data('flowerpower@example.org'))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['username'], 'flowerpower1')

    def test_rejects_duplicate_email(self):
        User.objects.create_user('someone', email='taken@example.com')
        form = SignupForm(data=signup_data('taken@example.com'))
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_rejects_mismatched_passwords(self):
        form = SignupForm(data=signup_data('new@example.com', confirm='Different@123'))
        self.assertFalse(form.is_valid())

    def test_requires_special_character_in_password(self):
        form = SignupForm(data=signup_data('new@example.com', password='Password123'))
        self.assertFalse(form.is_valid())
        self.assertIn('password1', form.errors)
