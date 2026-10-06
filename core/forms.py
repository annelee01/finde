from django import forms
from allauth.account.forms import SignupForm as BaseSignupForm
from django.contrib.auth.models import User
from .validators import validate_username, validate_name
from django.core.exceptions import ValidationError
from core.models import Profile
from .utils import make_username_unique
from .validators import validate_username, validate_name, validate_no_profanity, contains_special_character
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm, PasswordResetForm
from django.template import loader
from django.core.mail import EmailMultiAlternatives

class SignupForm(BaseSignupForm):
    def __init__(self, *args, **kwargs):
        super(SignupForm, self).__init__(*args, **kwargs)

        # Overriding the email field to ensure it is required
        self.fields['email'] = forms.EmailField(
            label=("Email"),
            required=True,  # Ensure email is required
            widget=forms.EmailInput(attrs={
                "placeholder": ("Email address"),
                "class": "w-full py-4 px-6 rounded-xl"
            }),
        )

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'Your email',
            'class': 'w-full py-4 px-6 rounded-xl'
        })
    )
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Your password',
            'class': 'w-full py-4 px-6 rounded-xl'
        })
    )

    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Confirm password',
            'class': 'w-full py-4 px-6 rounded-xl'
        }),
        label="Confirm password"
    )

    class Meta:
        model = User
        fields = ('first_name', 'email', 'password1')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('A user with that email already exists.')
        return email
    
    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        # Check for special character in both passwords
        if password1 or password2:
            if not password1 or not password2:
                raise ValidationError("Both password fields must be filled.")

            if password1 != password2:
                raise ValidationError("Passwords do not match.")

            if password1 and not contains_special_character(password1):
                self.add_error('password1', "The password must contain at least one special character.")
                
        # Automatically generate username from the email prefix
        email = cleaned_data.get('email')
        if email:
            username = email.split('@')[0]  # Extract the prefix of the email
            username = make_username_unique(username)  # Ensure username is unique
            cleaned_data['username'] = username  # Set the username in cleaned_dataow 

        return cleaned_data

# update the user model's information on account page
class UserForm(forms.ModelForm):
    first_name = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'w-full py-4 px-6 rounded-xl'
        }),
        validators=[validate_name, validate_no_profanity]
    )
    last_name = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'w-full py-4 px-6 rounded-xl'
        }),
        validators=[validate_name, validate_no_profanity]
    )
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'w-full py-4 px-6 rounded-xl'
        }),
        validators=[validate_username, validate_no_profanity]
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username']

    def clean(self):
        cleaned_data = super().clean()
        # Additional custom validation if needed
        return cleaned_data

# edit user profile information that is not part of the core user model
class ProfileForm(forms.ModelForm):
    delete_profile_picture = forms.BooleanField(required=False, initial=False)

    bio = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'placeholder': 'About me...',
            'id': 'id_bio',
            'class': 'form-input',
            'maxlength': '160',
        }),
        validators=[validate_no_profanity]
    )

    location = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'id': 'id_location',
            'class': 'form-input',
            'maxlength': '58',
        }),
        validators=[validate_no_profanity]
    )

    class Meta:
        model = Profile
        fields = ['bio', 'profile_picture', 'location']

class EmailUpdateForm(forms.ModelForm):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'Your email',
            'class': 'w-full py-4 px-6 rounded-xl'
        }),
        required=True
    )

    class Meta:
        model = User
        fields = ['email']

class CustomPasswordChangeForm(PasswordChangeForm):
    """Custom Password Change Form with optional password fields."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set the fields to not be required initially
        self.fields['old_password'].required = False
        self.fields['new_password1'].required = False
        self.fields['new_password2'].required = False

    def clean(self):
        cleaned_data = super().clean()

        old_password = cleaned_data.get("old_password")
        new_password1 = cleaned_data.get("new_password1")
        new_password2 = cleaned_data.get("new_password2")

        # Only validate passwords if any password field is filled
        if old_password or new_password1 or new_password2:
            # Make sure all fields are filled if any one is filled
            if not old_password or not new_password1 or not new_password2:
                raise ValidationError("All password fields must be filled if you want to change your password.")

            # Check for special character in new password
            if new_password1 and not contains_special_character(new_password1):
                self.add_error('new_password1', "The new password must contain at least one special character.")
                # You can also raise an error for new_password2 if needed
                self.add_error('new_password2', "The new password must contain at least one special character.")

            # Trigger built-in validators by calling the parent's clean methods
            super().clean()

        return cleaned_data

class CustomPasswordResetForm(PasswordResetForm):
    def send_mail(self, subject_template_name, email_template_name, 
                  context, from_email, to_email, html_email_template_name=None):
        """
        Override the default send_mail method to customize email sending
        with both HTML and plain text versions
        """
        subject = loader.render_to_string(subject_template_name, context)
        # Email subject *must not* contain newlines
        subject = ''.join(subject.splitlines())
        
        # Load the plain text content
        body = loader.render_to_string(email_template_name, context)
        
        # Create the email message
        email_message = EmailMultiAlternatives(subject, body, from_email, [to_email])
        
        # Attach HTML version if provided
        if html_email_template_name is not None:
            html_email = loader.render_to_string(html_email_template_name, context)
            email_message.attach_alternative(html_email, 'text/html')
        
        # Add any additional customization here (e.g., attachments)
        
        # Send the email
        email_message.send()
   
class CustomSetPasswordForm(SetPasswordForm):
    """Custom Set Password Form with optional fields."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set password fields to not be required initially
        self.fields['new_password1'].required = False
        self.fields['new_password2'].required = False

    def clean(self):
        cleaned_data = super().clean()

        new_password1 = cleaned_data.get("new_password1")
        new_password2 = cleaned_data.get("new_password2")

        # Validate passwords if any field is filled
        if new_password1 or new_password2:
            # Make sure both fields are filled if any is filled
            if not new_password1 or not new_password2:
                raise ValidationError("Both password fields must be filled out.")

            # Check for special character in new password
            if new_password1 and not contains_special_character(new_password1):
                self.add_error('new_password1', "The new password must contain at least one special character.")

            # Call super to trigger built-in validators
            super().clean()

        return cleaned_data
  
class VerificationCodeForm(forms.Form):
    code = forms.CharField(
        widget=forms.TextInput(attrs={
            'placeholder': '123456',
            'inputmode': 'numeric',  # Mobile keyboard shows numbers
        }),
        required=True,
        label="Enter verification code"
    )