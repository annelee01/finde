from rest_framework import serializers
from .models import ( 
    CoreEbayitem,
    MarketplaceItem, 
    Category, 
    MarketplaceItemImage, 
    Attribute, 
    MarketplaceItemAttribute
)


class eBayItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoreEbayitem
        fields = '__all__'

class CategorySerializer(serializers.ModelSerializer):
    """Serializer for Category model."""
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'parent', 'created_at']


class MarketplaceItemImageSerializer(serializers.ModelSerializer):
    """Serializer for MarketplaceItemImage model."""
    class Meta:
        model = MarketplaceItemImage
        fields = ['id', 'image', 'alt_text', 'is_primary', 'order', 'created_at']


class AttributeSerializer(serializers.ModelSerializer):
    """Serializer for Attribute model."""
    class Meta:
        model = Attribute
        fields = ['id', 'name', 'value']


class MarketplaceItemAttributeSerializer(serializers.ModelSerializer):
    """Serializer for MarketplaceItemAttribute model."""
    attribute = AttributeSerializer(read_only=True)
    
    class Meta:
        model = MarketplaceItemAttribute
        fields = ['attribute']


class MarketplaceItemSerializer(serializers.ModelSerializer):
    """Enhanced serializer for MarketplaceItem with detection support."""
    category_name = serializers.CharField(source='category.name', read_only=True)
    seller_username = serializers.CharField(source='seller.username', read_only=True)
    images = MarketplaceItemImageSerializer(many=True, read_only=True)
    attributes = MarketplaceItemAttributeSerializer(many=True, read_only=True)
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False
    )
    detection_results = serializers.JSONField(write_only=True, required=False)
    auto_crop = serializers.BooleanField(write_only=True, required=False, default=False)
    auto_enhance = serializers.BooleanField(write_only=True, required=False, default=False)
    
    class Meta:
        model = MarketplaceItem
        fields = [
            'id', 'item_id', 'title', 'description', 'price', 'color', 'size',
            'category', 'category_name', 'brand', 'material', 'seller_username',
            'us_shoe_size', 'shoe_size_width', 'hat_size', 'chest_size',
            'bra_size', 'waist_size', 'inseam', 'hip_size', 'waist_to_hem',
            'shoulder_to_shoulder', 'shoulder_to_hem', 'women_size',
            'bottoms_size', 'ring_size', 'necklace_length', 'item_length',
            'created_at', 'updated_at', 'is_active', 'images', 'attributes',
            'uploaded_images', 'detection_results', 'auto_crop', 'auto_enhance'
        ]
        read_only_fields = ['item_id', 'created_at', 'updated_at']

    def validate_price(self, value):
        """Validate that price is positive."""
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than 0.")
        return value

    def validate_uploaded_images(self, value):
        """Validate uploaded images."""
        if len(value) > 9:
            raise serializers.ValidationError("Maximum 9 images allowed.")
        
        for image in value:
            # Validate file size (max 10MB)
            if image.size > 10 * 1024 * 1024:
                raise serializers.ValidationError(
                    f"Image {image.name} is too large. Maximum size is 10MB."
                )
            
            # Validate file type
            allowed_types = ['image/jpeg', 'image/png', 'image/webp']
            if image.content_type not in allowed_types:
                raise serializers.ValidationError(
                    f"Image {image.name} has invalid format. "
                    "Allowed formats: JPEG, PNG, WebP."
                )
        
        return value

    def create(self, validated_data):
        """Create MarketplaceItem with enhanced processing."""
        # Remove fields that aren't part of the model
        uploaded_images = validated_data.pop('uploaded_images', [])
        detection_results = validated_data.pop('detection_results', None)
        auto_crop = validated_data.pop('auto_crop', False)
        auto_enhance = validated_data.pop('auto_enhance', False)
        
        # Create the item
        item = MarketplaceItem.objects.create(**validated_data)
        
        # Store processing flags for the view to use
        item._uploaded_images = uploaded_images
        item._detection_results = detection_results
        item._auto_crop = auto_crop
        item._auto_enhance = auto_enhance
        
        return item

    def to_representation(self, instance):
        """Enhanced representation with additional computed fields."""
        data = super().to_representation(instance)
        
        # Add computed fields
        data['primary_image'] = None
        if instance.images.exists():
            primary_img = instance.images.filter(is_primary=True).first()
            if primary_img:
                data['primary_image'] = primary_img.image.url if hasattr(primary_img.image, 'url') else str(primary_img.image)
        
        # Add detected categories for filtering
        detected_categories = []
        for attr in instance.attributes.filter(attribute__name='Detected Item Type'):
            detected_categories.append(attr.attribute.value)
        data['detected_categories'] = detected_categories
        
        # Add size information summary
        size_info = {}
        size_fields = [
            'us_shoe_size', 'shoe_size_width', 'hat_size', 'chest_size',
            'bra_size', 'waist_size', 'inseam', 'hip_size', 'waist_to_hem',
            'shoulder_to_shoulder', 'shoulder_to_hem', 'women_size',
            'bottoms_size', 'ring_size', 'necklace_length', 'item_length'
        ]
        
        for field in size_fields:
            value = getattr(instance, field)
            if value:
                # Convert field name to readable format
                readable_name = field.replace('_', ' ').title()
                size_info[readable_name] = value
        
        data['detailed_sizing'] = size_info
        
        # Add category path
        if instance.category:
            data['category_path'] = instance.category.get_path()
        
        return data


class BulkMarketplaceItemSerializer(serializers.Serializer):
    """Serializer for bulk item creation from CSV."""
    csv_file = serializers.FileField()
    
    def validate_csv_file(self, value):
        """Validate CSV file."""
        if not value.name.endswith('.csv'):
            raise serializers.ValidationError("File must be a CSV file.")
        
        if value.size > 5 * 1024 * 1024:  # 5MB limit
            raise serializers.ValidationError("CSV file too large. Maximum size is 5MB.")
        
        return value


class DetectionOnlySerializer(serializers.Serializer):
    """Serializer for detection-only requests."""
    image = serializers.ImageField()
    
    def validate_image(self, value):
        """Validate image for detection."""
        # Validate file size (max 10MB)
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("Image is too large. Maximum size is 10MB.")
        
        # Validate file type
        allowed_types = ['image/jpeg', 'image/png', 'image/webp']
        if value.content_type not in allowed_types:
            raise serializers.ValidationError(
                "Invalid image format. Allowed formats: JPEG, PNG, WebP."
            )
        
        return value


class FilterSerializer(serializers.Serializer):
    """Serializer for advanced filtering options."""
    category = serializers.CharField(required=False)
    detected_type = serializers.CharField(required=False)
    min_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    max_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    color = serializers.CharField(required=False)
    size = serializers.CharField(required=False)
    brand = serializers.CharField(required=False)
    material = serializers.CharField(required=False)
    search = serializers.CharField(required=False)
    
    # Size-specific filters
    us_shoe_size = serializers.CharField(required=False)
    women_size = serializers.CharField(required=False)
    
    def validate(self, data):
        """Validate filter data."""
        min_price = data.get('min_price')
        max_price = data.get('max_price')
        
        if min_price and max_price and min_price > max_price:
            raise serializers.ValidationError(
                "Minimum price cannot be greater than maximum price."
            )
        
        return data