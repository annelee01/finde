from allauth.socialaccount.models import SocialApp, SocialAccount, SocialToken
from allauth.socialaccount.admin import SocialAppAdmin, SocialAccountAdmin, SocialTokenAdmin
from django.contrib import admin
from django_otp.admin import OTPAdminSite
from django.contrib.auth.models import User
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp.plugins.otp_totp.admin import TOTPDeviceAdmin
from django.contrib.sites.models import Site
from django.contrib.sites.admin import SiteAdmin
from .models import Category, MarketplaceItemImage

# Create custom admin site instance
admin_site = OTPAdminSite(name='OTPAdmin')

# Register default models
admin_site.register(User)
admin_site.register(TOTPDevice, TOTPDeviceAdmin)
admin_site.register(Site, SiteAdmin)

# Register allauth social account models
admin_site.register(SocialApp, SocialAppAdmin)
admin_site.register(SocialAccount, SocialAccountAdmin)
admin_site.register(SocialToken, SocialTokenAdmin)


class MarketplaceItemImageInline(admin.TabularInline):
    model = MarketplaceItemImage
    extra = 1
    fields = ['image', 'alt_text', 'is_primary', 'order']


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'created_at']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']
