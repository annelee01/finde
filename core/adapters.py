from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings
from django.template.loader import render_to_string
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMultiAlternatives
import random
import string

# custom email adapter to override django-allauth's default email behavior
class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Custom adapter for allauth to improve email deliverability and customize the user experience.
    """
    
    def send_confirmation_mail(self, request, emailconfirmation, signup):
        """
        Overrides the send_confirmation_mail method to customize the confirmation email.
        """
        current_site = get_current_site(request)  # Use Django's default method
        activate_url = self.get_email_confirmation_url(request, emailconfirmation)
        ctx = {
            "user": emailconfirmation.email_address.user,
            "activate_url": activate_url,
            "current_site": current_site,
            "key": emailconfirmation.key,
            "site_name": current_site.name if hasattr(current_site, 'name') else current_site.domain,
            "site_domain": current_site.domain,
        }

        # Add user's name to context if available
        try:
            if hasattr(emailconfirmation.email_address.user, 'first_name') and emailconfirmation.email_address.user.first_name:
                ctx['name'] = emailconfirmation.email_address.user.first_name
        except:
            pass

        if signup:
            email_template = 'account/email/email_confirmation_signup'
        else:
            email_template = 'account/email/email_confirmation'
            
        self.send_mail(email_template, emailconfirmation.email_address.email, ctx)
    
    def send_mail(self, template_prefix, email, context):
        """
        Sends an email with custom headers to improve deliverability.
        """
        subject = render_to_string(f'{template_prefix}_subject.txt', context)
        # Remove newlines to prevent header injection
        subject = " ".join(subject.splitlines()).strip()
        
        # Plain text version (required for best deliverability)
        text_body = render_to_string(f'{template_prefix}_message.txt', context)
        
        # HTML version (nice to have but not required)
        try:
            html_body = render_to_string(f'{template_prefix}_message.html', context)
            has_html = True
        except:
            html_body = None
            has_html = False
        
        # Add a reference ID for tracking/troubleshooting
        # Generate a random reference ID for this email
        ref_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        
        # Create the email message
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL_WITH_NAME', settings.DEFAULT_FROM_EMAIL),
            to=[email]
        )
        
        # Add custom headers to improve deliverability
        msg.extra_headers = {
            # Clear identification of the sender
            "From": getattr(settings, 'DEFAULT_FROM_EMAIL_WITH_NAME', settings.DEFAULT_FROM_EMAIL),
            
            # Proper reply-to address
            "Reply-To": settings.DEFAULT_FROM_EMAIL,
            
            # Message ID helps with threading and avoiding duplication detection
            "Message-ID": f"<{ref_id}@{settings.DEFAULT_FROM_EMAIL.split('@')[1]}>",
            
            # Normal priority
            "X-Priority": "3",
            
            # Helps email clients understand this is a transactional email, not marketing
            "X-Mailer": "Finde Email Service",
            
            # Required by law for commercial emails in many jurisdictions
            "List-Unsubscribe": f"<mailto:unsubscribe@{settings.DEFAULT_FROM_EMAIL.split('@')[1]}>",
        }
        
        # If we have an HTML version, attach it as an alternative
        if has_html:
            msg.attach_alternative(html_body, "text/html")
            
        return msg.send()