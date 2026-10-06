import re, os
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from allauth.socialaccount.models import SocialAccount
from django.utils.html import format_html

# Load the custom wordlist
file_path = os.path.join(os.path.dirname(__file__), 'static/data/profanity_wordlist.txt')
with open(file_path) as f:
    PROFANITY_WORDLIST = set(f.read().splitlines())

def contains_profanity(value):
    words = re.findall(r'\b\w+\b', value.lower())
    return any(word in PROFANITY_WORDLIST for word in words)

def validate_no_profanity(value):
    if not re.match(r'^[a-zA-Z0-9._-]+$', value): # Skip profanity check if the value contains invalid characters
        return
    if contains_profanity(value):
        raise ValidationError('This field contains inappropriate language.')

def validate_username(value):
    if not re.match(r'^[\w.]+$', value):
        raise ValidationError(
            'Username can only contain letters, digits, underscores, and periods.'
        )
    if not (3 <= len(value) <= 15):
        raise ValidationError(
            'Username must be between 3 and 15 characters long.'
        )

def validate_name(value):
    if not re.match(r'^[A-Za-z-]+$', value):
        raise ValidationError(
            'Name can only contain alphabet characters and hyphens.'
        )

def validate_login_input(login_input, password):
    # Validate email or username input
    if '@' in login_input:
        try:
            user = User.objects.get(email=login_input)
        except User.DoesNotExist:
            return "No user found with this email. Please try again."
        
        # Check if the user has a social account and no usable password
        if SocialAccount.objects.filter(user=user).exists() and not user.has_usable_password():
            return format_html(
                'You signed up with Google. Please sign in with your <strong><a href="{}">Google account</a>.</strong>',
                '/accounts/google/login/'  # Adjust this path if necessary
            )
        
        # Validate password
        if not authenticate(username=user.username, password=password):
            return "Incorrect password for this email. Please try again."
    
    else:
        try:
            user = User.objects.get(username=login_input)
        except User.DoesNotExist:
            return "No user found with this username. Please try again."
        
        # Validate password
        if not authenticate(username=login_input, password=password):
            return "Incorrect password for this username. Please try again."
    
    return None  # No errors
    
def contains_special_character(password):
    """Check if the password contains at least one special character."""
    return bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', password))
