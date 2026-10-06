"""Sign-up, login, account settings, email verification and password reset."""

import logging
import random
from io import BytesIO

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    login,
    update_session_auth_hash,
    get_user_model,
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User
from django.contrib.auth.views import PasswordResetView
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.http import HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.utils.safestring import mark_safe
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect

import requests
from PIL import Image
from allauth.account.models import EmailAddress
from allauth.account.utils import send_email_confirmation
from django_ratelimit.decorators import ratelimit

from ..forms import (
    UserForm,
    ProfileForm,
    SignupForm,
    VerificationCodeForm,
    EmailUpdateForm,
    CustomPasswordChangeForm,
    CustomSetPasswordForm,
)
from ..models import CoreEbayitem, FavoriteItem
from ..validators import validate_login_input

from ..image_utils import resize_image

from .favorites import get_favorite_items

logger = logging.getLogger(__name__)


def verify_recaptcha(recaptcha_response):
    """Verify the reCAPTCHA response with Google's API."""
    payload = {
        'secret': settings.RECAPTCHA_SECRET_KEY,
        'response': recaptcha_response
    }
    response = requests.post('https://www.google.com/recaptcha/api/siteverify', data=payload)
    result = response.json()
    return result.get('success')

@never_cache
@ratelimit(key='ip', rate='5/m', method='POST', block=True)  # 5 attempts per minute
@csrf_protect
def signup(request):
    if getattr(request, 'limited', False):
        return render(request, 'errors/rate_limit_exceeded.html')

    if request.method == 'POST':
        recaptcha_response = request.POST.get('g-recaptcha-response')
        if not verify_recaptcha(recaptcha_response):
            return HttpResponseBadRequest('Invalid reCAPTCHA. <a href="javascript:window.history.back()">Please try again.</a>')

        form = SignupForm(request.POST)

        if form.is_valid():
            user = form.save()  # Create the new user
            EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=False)
            send_email_confirmation(request, user)  # Send confirmation email
            messages.success(request, 'Email confirmation sent. Please confirm your email address to complete the signup process.')
            return redirect('core:browse')  # Redirect to 'core:browse'

    else:
        form = SignupForm()

    return render(request, 'core/signup.html', {'form': form})

@never_cache
@ratelimit(key='ip', rate='5/m', method='POST', block=True)  # 5 attempts per minute
@login_required
def account_view(request):
    if getattr(request, 'limited', False):
        return render(request, 'errors/rate_limit_exceeded.html')  # Render rate_limit.html template

    if request.method == "POST":
        user_form = UserForm(request.POST, instance=request.user)

        # Create a copy of request.FILES and remove the image field
        files = request.FILES.copy()
        profile_picture = files.get('profile_picture', None)

        # Remove the image so the form doesn't save it
        if 'profile_picture' in files:
            del files['profile_picture']

        profile_form = ProfileForm(request.POST, files, instance=request.user.profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile = profile_form.save(commit=False)

            # Handle profile picture deletion
            if profile_form.cleaned_data.get('delete_profile_picture'):
                if profile.profile_picture:
                    profile.profile_picture.delete(save=False)
                profile.profile_picture = None

            # Handle custom image processing
            if profile_picture:
                image = Image.open(profile_picture)
                image = resize_image(image, size=(400, 400))

                temp_file = BytesIO()

                # Check if image has transparency (RGBA)
                if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
                    # Save as PNG if it has transparency
                    image.save(temp_file, format='PNG')
                else:
                    # Otherwise, save as JPEG (without transparency)
                    image.save(temp_file, format='JPEG')

                temp_file.seek(0)

                profile.profile_picture.save(
                    profile_picture.name, ContentFile(temp_file.read()), save=False
                )

            profile.save()
            messages.success(request, 'Your profile was successfully updated!')
            return redirect('core:account')

        else:
            messages.error(request, 'Please correct the error below.')
    else:
        user_form = UserForm(instance=request.user)
        profile_form = ProfileForm(instance=request.user.profile)

    return render(request, 'core/account.html', {
        'user_form': user_form,
        'profile_form': profile_form
    })

def send_verification_code(user, request, new_email=None):
    verification_code = random.randint(100000, 999999)
    request.session['verification_code'] = verification_code
    request.session['new_email'] = new_email  # Store the new email temporarily in session

    # Send the verification code to the current email (user.email)
    send_mail(
        'Your Verification Code',
        f'Your verification code is: {verification_code}',
        'hello@finde.clothing',
        [user.email],  # Send to the current email, not the new email
        fail_silently=False,
    )

    # Send success message
    if new_email:
        messages.success(request, f'A verification code has been sent to your current email before changing it to {new_email}.')
    else:
        messages.success(request, 'A verification code has been sent to your current email.')

# Step 2: Verify the code entered by the user.
@login_required
def verify_code(request):
    if request.method == "POST":
        form = VerificationCodeForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code']
            if str(code) == str(request.session.get('verification_code')):
                new_email = request.session.get('new_email')
                new_password = request.session.get('new_password')

                user = request.user

                if new_email:
                    # Update the user's email
                    user.email = new_email
                    user.save()
                    del request.session['new_email']
                    messages.success(request, 'Your email has been successfully updated!')

                if new_password:
                    # Update the user's password
                    user.set_password(new_password)
                    user.save()
                    update_session_auth_hash(request, user)  # Keep the user logged in after password change
                    del request.session['new_password']
                    messages.success(request, 'Your password has been successfully updated!')

                del request.session['verification_code']
                return redirect('core:account_management')  # Redirect to account management page

            else:
                messages.error(request, 'Invalid verification code. Please try again.')

    else:
        form = VerificationCodeForm()

    # Optionally allow resending of the code
    if request.GET.get('action') == 'resend':
        send_verification_code(request.user, request)
        return redirect('core:verify_code')

    return render(request, 'account/verify-code.html', {'form': form})

@never_cache
@ratelimit(key='ip', rate='5/m', method='POST', block=False)  # 5 attempts per minute
@login_required
def account_management(request):
    if getattr(request, 'limited', False):
        return render(request, 'errors/rate_limit_exceeded.html')  # Render rate_limit.html template

    user = request.user

    # Initialize forms
    email_form = EmailUpdateForm(instance=user)
    password_form = CustomPasswordChangeForm(user) if user.has_usable_password() else CustomSetPasswordForm(user)
    user_form = UserForm(instance=user)

    if request.method == "POST":
        recaptcha_response = request.POST.get('g-recaptcha-response')
        if not verify_recaptcha(recaptcha_response):
            return HttpResponseBadRequest('Invalid reCAPTCHA. <a href="javascript:window.history.back()">Please try again.</a>')

        # Check if the email form is being submitted
        if request.POST.get('email_change') == '1':
            email_form = EmailUpdateForm(request.POST)
            if email_form.is_valid():
                new_email = email_form.cleaned_data['email']

                if new_email == user.email:
                    messages.error(request, "The new email cannot be the same as the current email.")
                else:
                    # Send verification code to new email
                    send_verification_code(user, request, new_email=new_email)
                    return redirect('core:verify_code')  # Redirect to verification page

        # Check if the password form is being submitted
        elif request.POST.get('password_change') == '1':
            password_form = CustomPasswordChangeForm(user, request.POST) if user.has_usable_password() else CustomSetPasswordForm(user, request.POST)
            if password_form.is_valid():
                new_password = password_form.cleaned_data['new_password1']

                if check_password(new_password, user.password):
                    messages.error(request, 'You cannot use your previous password.')
                else:
                    # Store the new password in session and send verification code
                    request.session['new_password'] = new_password
                    send_verification_code(user, request)  # No new email passed here
                    return redirect('core:verify_code')  # Redirect to verification page
            else:
                messages.error(request, 'Please correct the password errors below.')

        # If neither form was valid, show form errors
        else:
            messages.error(request, 'Please correct the errors below.')

    return render(request, 'account/account-management.html', {
        'email_form': email_form,
        'password_form': password_form,
        'user_form': user_form,
        'has_password': user.has_usable_password(),
    })

@never_cache
def profile_view(request, username):
    user = get_object_or_404(User, username=username)

    # Get user's favorite items using the helper function
    favorite_items = get_favorite_items(user)

    # Separate queries for IN_STOCK, ENDED, and OUT_OF_STOCK items, sorted by favorited_at
    in_stock_items = favorite_items.filter(availability='IN_STOCK').order_by('-favorited_at')
    ended_items = favorite_items.filter(availability='ENDED').order_by('-favorited_at')
    sold_items = favorite_items.filter(availability='OUT_OF_STOCK').order_by('-favorited_at')

    favorited_items_ids = FavoriteItem.objects.filter(user=user, is_favorited=True).values_list('item_id', flat=True)
    favorited_items = CoreEbayitem.objects.filter(item_id__in=favorited_items_ids)

      # Get favorited item IDs for the logged-in user, if they are authenticated
    logged_in_user_favorited_ids = []
    if request.user.is_authenticated:
        logged_in_user_favorited_ids = FavoriteItem.objects.filter(
            user=request.user, is_favorited=True
        ).values_list('item_id', flat=True)
        logger.debug(logged_in_user_favorited_ids)

    context = {
        'user': user,
        'in_stock_items': in_stock_items,  # Pass IN_STOCK items to the template
        'ended_items': ended_items,  # Pass ENDED items to the template
        'sold_items': sold_items, # Pass OUT_OF_STOCK items to the template
        'favorited_items': favorited_items,
        'logged_in_user_favorited_ids': logged_in_user_favorited_ids,
    }

    return render(request, 'core/profile.html', context)

@never_cache
@ratelimit(key='ip', rate='5/m', method='POST', block=False)  # 5 attempts per minute
def login_user(request):
    if getattr(request, 'limited', False):
        return render(request, 'errors/rate_limit_exceeded.html')  # Render rate_limit.html template

    if request.method == "POST":
        recaptcha_response = request.POST.get('g-recaptcha-response')
        if not verify_recaptcha(recaptcha_response):
            return HttpResponseBadRequest('Invalid reCAPTCHA. <a href="javascript:window.history.back()">Please try again.</a>')

        login_input = request.POST['login_input']
        password = request.POST['password']

        # Validate login input
        error_message = validate_login_input(login_input, password)
        if error_message:
            return render(request, 'account/login.html', {'error_message': error_message})

        # Determine if login_input is an email
        is_email = '@' in login_input
        if is_email:
            try:
                user = User.objects.get(email=login_input)
            except User.DoesNotExist:
                return render(request, 'account/login.html', {'error_message': "No user found with this email. Please try again."})
        else:
            try:
                user = User.objects.get(username=login_input)
            except User.DoesNotExist:
                return render(request, 'account/login.html', {'error_message': "No user found with this username. Please try again."})

         # Check if the email is verified
        email_address = EmailAddress.objects.filter(user=user, email=user.email).first()
        if email_address:
            if not email_address.verified:
                # Check if the user signed up using Google
                if user.socialaccount_set.exists():
                    return render(request, 'account/login.html', {
                        'error_message': "This email was used to sign up with Google. <a href='{% url 'google_login' %}'>Log in with Google</a>"
                    })

                # Automatically send the verification code
                send_verification_code(user, request)

                # Show the error message
                return render(request, 'account/login.html', {
                    'error_message': "Please check your email and follow the link to verify your email address before logging in."
                })

        # Authenticate user
        user = authenticate(request, username=user.username, password=password)
        if user is not None:
            login(request, user)
            return redirect('core:browse')
        else:
            return render(request, 'account/login.html', {'error_message': "Incorrect password. Please try again."})
    else:
        return render(request, 'account/login.html')


# If user signed up via google, (they didnt create a password), and then request a reset password, display error message and redirect to login with google
User = get_user_model()
class CustomPasswordResetView(PasswordResetView):
    template_name = 'account/password_reset.html'
    success_url = reverse_lazy('password_reset_done')

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            email = form.cleaned_data['email']

            # Check if user exists and has a password
            try:
                user = User.objects.get(email=email)
                # Check if user has a usable password (not OAuth user)
                if not user.has_usable_password():
                    # Generate the Google login URL
                    login_url = reverse('account_login')

                    # User signed up with OAuth, doesn't have a password
                    error_message = mark_safe(
                        f"This account was created using Google Sign-In. Please  "
                        f"<a href='{login_url}' style='text-decoration: underline; padding:.2rem;'>"
                        f"log in with Google</a> and change your password in Account Settings."
                    )
                    messages.error(request, error_message)

                    return render(request, self.template_name, {'form': form})
            except User.DoesNotExist:
                # Don't reveal if email exists or not for security
                pass

            # If we get here, either user has password or doesn't exist
            # Let Django handle it normally
            return self.form_valid(form)
        else:
            return self.form_invalid(form)
