from django.db import models
from finde.find_relistedItemId import check_item_availability
from django.utils import timezone
from django.utils.timezone import make_aware
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models.signals import post_save

import uuid
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
import logging

logger = logging.getLogger(__name__)

class ShoeSizeConversion(models.Model):
    foot_length_in = models.FloatField(max_length=50, null=True, blank=True)
    us_shoe_size = models.CharField(max_length=50, null=True, blank=True)  
    europe_shoe_size = models.CharField(max_length=50, null=True, blank=True)  
    uk_shoe_size = models.CharField(max_length=50, null=True, blank=True) 
    france_shoe_size = models.CharField(max_length=50, null=True, blank=True)  
    japan_shoe_size = models.CharField(max_length=50, null=True, blank=True) 
    korea_china_shoe_size = models.CharField(max_length=50, null=True, blank=True) 

    def __str__(self):
        return f"Shoe Size Conversion for {self.foot_length_in} inches"

# -------------------
# Category System
# -------------------
class Category(models.Model):
    """Hierarchical categories for MarketplaceItems."""
    name = models.CharField(max_length=255)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children"
    )

    slug = models.SlugField(unique=True)  # This field is missing
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    def get_path(self):
        """Return full path like 'Clothing > Women > Dresses'."""
        path = []
        node = self
        while node:
            path.append(node.name)
            node = node.parent
        return " > ".join(reversed(path))


# -------------------
# Marketplace Items
# -------------------
class MarketplaceItem(models.Model):
    """Items uploaded directly by users into the marketplace."""
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name="listings")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    color = models.CharField(max_length=50, blank=True)
    size = models.CharField(max_length=50, blank=True)
    item_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    brand = models.CharField(max_length=50, blank=True)
    material = models.CharField(max_length=50, blank=True)

    # Sizing
    us_shoe_size = models.CharField(max_length=50, null=True, blank=True)
    shoe_size_width = models.CharField(max_length=50, null=True, blank=True)
    shoe_size_conversion = models.ForeignKey("ShoeSizeConversion", null=True, blank=True, on_delete=models.SET_NULL)
    hat_size = models.CharField(max_length=10, null=True, blank=True)
    chest_size = models.CharField(max_length=50, null=True, blank=True)
    bra_size = models.CharField(max_length=50, null=True, blank=True)
    waist_size = models.CharField(max_length=50, null=True, blank=True)
    inseam = models.CharField(max_length=50, null=True, blank=True)
    hip_size = models.CharField(max_length=50, null=True, blank=True)
    waist_to_hem = models.CharField(max_length=50, null=True, blank=True)
    shoulder_to_shoulder = models.CharField(max_length=50, null=True, blank=True)
    shoulder_to_hem = models.CharField(max_length=50, null=True, blank=True)
    women_size = models.CharField(max_length=50, null=True, blank=True)
    bottoms_size = models.CharField(max_length=50, null=True, blank=True)
    ring_size = models.CharField(max_length=50, null=True, blank=True)
    necklace_length = models.CharField(max_length=50, null=True, blank=True)
    item_length = models.CharField(max_length=50, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.title} ({self.seller.username})"


# -------------------
# Attribute / Filter System
# -------------------
class Attribute(models.Model):
    """Defines a filterable attribute type and its value."""
    name = models.CharField(max_length=255)   # e.g., "Silhouette", "Earring Type"
    value = models.CharField(max_length=255)  # e.g., "Bias", "Clip-On", "Chandelier"

    class Meta:
        unique_together = ('name', 'value')  # Prevent duplicate entries

    def __str__(self):
        return f"{self.name}: {self.value}"


class MarketplaceItemAttribute(models.Model):
    """Links MarketplaceItems to filterable Attributes (many-to-many)."""
    item = models.ForeignKey(MarketplaceItem, on_delete=models.CASCADE, related_name="attributes")
    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('item', 'attribute')  # Prevent duplicates

    def __str__(self):
        return f"{self.item.title} -> {self.attribute}"

class MarketplaceItemImage(models.Model):
    """Images for marketplace items."""
    item = models.ForeignKey(MarketplaceItem, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='marketplace/images/%Y/%m/%d/')
    alt_text = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.item.title}"

    class Meta:
        ordering = ['order', 'created_at']




# Create Listings Image Temp Storage

from datetime import timedelta

class TempImage(models.Model):
    """Temporary image storage for listing creation process"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_key = models.CharField(max_length=100, db_index=True)
    image = models.ImageField(upload_to='temp_images/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    batch_id = models.CharField(max_length=100, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['session_key', 'batch_id']),
            models.Index(fields=['expires_at']),
        ]
        ordering = ['uploaded_at']
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            # Set expiration to 24 hours from now
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    @property
    def image_url(self):
        """Return the full S3 URL for the image"""
        if self.image:
            return self.image.url
        return None
    
    def __str__(self):
        return f"TempImage {self.id} - Session: {self.session_key}"
    



class CoreEbayitem(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    featured = models.BooleanField(default=False)
    gallery_url = models.TextField(max_length=2048)
    title = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2) 
    color = models.CharField(max_length=50)
    size = models.CharField(max_length=50)
    item_id = models.CharField(max_length=255, unique=True)
    item_web_url = models.TextField(max_length=2048)
    availability = models.CharField(max_length=50)
    itemCreationDate = models.CharField(max_length=50)
    itemEndDate = models.CharField(max_length=50)
    categoryId = models.CharField(max_length=50)
    categoryIdPath = models.CharField(max_length=100)
    us_shoe_size = models.CharField(max_length=50, null=True, blank=True)
    shoe_size_width = models.CharField(max_length=50, null=True, blank=True)  
    shoe_size_conversion = models.ForeignKey(ShoeSizeConversion, null=True, blank=True, on_delete=models.SET_NULL)
    hat_size = models.CharField(max_length=10, null=True, blank=True)  
    chest_size = models.CharField(max_length=50, null=True, blank=True)
    bra_size = models.CharField(max_length=50, null=True, blank=True)    
    waist_size = models.CharField(max_length=50, null=True, blank=True) 
    inseam = models.CharField(max_length=50, null=True, blank=True)  
    hip_size = models.CharField(max_length=50, null=True, blank=True) 
    waist_to_hem = models.CharField(max_length=50, null=True, blank=True) 
    shoulder_to_shoulder = models.CharField(max_length=50, null=True, blank=True)  
    shoulder_to_hem = models.CharField(max_length=50, null=True, blank=True) 
    women_size = models.CharField(max_length=50, null=True, blank=True) 
    bottoms_size = models.CharField(max_length=50, null=True, blank=True) 
    ring_size = models.CharField(max_length=50, null=True, blank=True) 
    necklace_length = models.CharField(max_length=50, null=True, blank=True)
    item_length = models.CharField(max_length=50, null=True, blank=True) 
    material = models.CharField(max_length=50, null=True, blank=True) 
    brand = models.CharField(max_length=50, null=True, blank=True)
    user_id = models.CharField(max_length=50, null=True, blank=True)
    username = models.CharField(max_length=64, null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'core_ebayitem'

    shoe_size_conversion = models.ForeignKey(
        'ShoeSizeConversion', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True
    )
    
    def update_availability_status(self):
        """
        Updates the item details and availability status based on the provided dictionary 
        from the check_item_availability function.
        """
        try:
            # Fetch item availability details
            item_details = check_item_availability(self.item_id)

            if item_details and not item_details.get('error'):
                
                # Get availability status directly - it's already extracted!
                estimated_availability = item_details.get('availability_status', 'Unknown')
                self.availability = estimated_availability

                # Update the item end date if it exists
                item_end_date_str = item_details.get('itemEndDate')
                if item_end_date_str:
                    # Convert to database format
                    item_end_date = make_aware(timezone.datetime.strptime(item_end_date_str, '%Y-%m-%dT%H:%M:%S.%fZ'))
                    self.itemEndDate = item_end_date.strftime('%Y-%m-%d %H:%M:%S')

                # Update item web URL
                if item_details.get('item_web_url'):
                    self.item_web_url = item_details['item_web_url']

                # If OUT_OF_STOCK, save and return early
                if self.availability == 'OUT_OF_STOCK':
                    self.save()
                    return

                # Only check for ENDED if not OUT_OF_STOCK
                if item_end_date_str:
                    current_datetime = timezone.now()
                    if item_end_date < current_datetime:
                        self.availability = 'ENDED'

                # Note: title and price are NOT returned by check_item_availability
                # Remove these lines or modify check_item_availability to return them
                # self.title = item_details.get('title', self.title)
                # price_value = item_details.get('price', {}).get('value')

                # Save all changes to the database
                self.save()

        except Exception as e:
            logger.error(f"Error updating item details for item {self.item_id}: {e}")
            import traceback
            logger.exception("Unhandled exception")


class CoreEbayitemSold(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    featured = models.BooleanField(default=False)
    gallery_url = models.TextField(max_length=2048)
    title = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2) 
    color = models.CharField(max_length=50)
    size = models.CharField(max_length=50)
    item_id = models.CharField(max_length=255)
    item_web_url = models.TextField(max_length=2048)
    availability = models.CharField(max_length=50)
    itemCreationDate = models.CharField(max_length=50)
    itemEndDate = models.CharField(max_length=50)
    categoryId = models.CharField(max_length=50)
    categoryIdPath = models.CharField(max_length=100)
    us_shoe_size = models.CharField(max_length=50, null=True, blank=True)
    shoe_size_width = models.CharField(max_length=10, null=True, blank=True)  
    shoe_size_conversion = models.ForeignKey(ShoeSizeConversion, null=True, blank=True, on_delete=models.SET_NULL)
    hat_size = models.CharField(max_length=10, null=True, blank=True)  
    chest_size = models.CharField(max_length=50, null=True, blank=True)
    bra_size = models.CharField(max_length=50, null=True, blank=True)  
    waist_size = models.CharField(max_length=50, null=True, blank=True)  
    hip_size = models.CharField(max_length=50, null=True, blank=True) 
    waist_to_hem = models.CharField(max_length=50, null=True, blank=True) 
    inseam = models.CharField(max_length=50, null=True, blank=True) 
    shoulder_to_shoulder = models.CharField(max_length=50, null=True, blank=True)  
    shoulder_to_hem = models.CharField(max_length=50, null=True, blank=True) 
    women_size = models.CharField(max_length=50, null=True, blank=True) 
    bottoms_size = models.CharField(max_length=50, null=True, blank=True) 
    ring_size = models.CharField(max_length=50, null=True, blank=True) 
    necklace_length = models.CharField(max_length=50, null=True, blank=True)  
    item_length = models.CharField(max_length=50, null=True, blank=True) 
    material = models.CharField(max_length=50, null=True, blank=True) 
    brand = models.CharField(max_length=50, null=True, blank=True) 
    user_id = models.CharField(max_length=50, null=True, blank=True)
    username = models.CharField(max_length=64, null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'core_ebayitem_out_of_stock'
    
    

class Timestamp(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)


def profile_picture_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    return f"profile_pictures/{uuid.uuid4()}.{ext}"

def validate_image_size(file):
    max_size_mb = 5
    try:
        if file.size > max_size_mb * 1024 * 1024:
            raise ValidationError(f"Image file too large ( > {max_size_mb}MB )")
    except FileNotFoundError:
        # Log it or just pass silently
        logger.warning(f"File not found: {file.name}")
        pass  # Or optionally raise a different warning
 


def validate_image_format(image):
    allowed_extensions = ['jpg', 'jpeg', 'png']
    ext = image.name.split('.')[-1].lower()
    if ext not in allowed_extensions:
        raise ValidationError("Supported formats: JPG, PNG")


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(max_length=160, blank=True) # Bio character limit set to 160. Limit set in forms.py
    profile_picture = models.ImageField(
        upload_to=profile_picture_upload_path,
        validators=[validate_image_size, validate_image_format],
        blank=True,
        null=True
    )
    location = models.CharField(max_length=58, blank=True)

    def __str__(self):
        return self.user.username

    def clean(self):
        super().clean()  # Call the parent's clean method
  
    def save(self, *args, **kwargs):
        # Check if this is an update to an existing profile
        if self.pk:
            old_profile = Profile.objects.get(pk=self.pk)

            # Check if the profile picture is being changed
            if old_profile.profile_picture and self.profile_picture != old_profile.profile_picture:
                # Use storage backend's delete method
                if default_storage.exists(old_profile.profile_picture.name):
                    default_storage.delete(old_profile.profile_picture.name)

        super().save(*args, **kwargs)

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()

class FavoriteItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    item_id = models.CharField(max_length=255, null=True)
    is_favorited = models.BooleanField(default=False)
    favorited_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'auth_user_favorited_items'
        unique_together = ('user', 'item_id')

    def __str__(self):
        return f"User: {self.user.username}, Item: {self.item_id}, Favorited: {self.is_favorited}, Favorited At: {self.favorited_at}"


class EmailCapture(models.Model):
    email = models.EmailField(max_length=255, unique=True)  
    newsletter_trend = models.BooleanField(default=False)
    captured_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email
