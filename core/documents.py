# documents.py for elasticsearch of coreebayitem data fields
from django_opensearch_dsl import Document, fields
from django_opensearch_dsl.registries import registry
from .models import CoreEbayitem, FavoriteItem
from opensearchpy.exceptions import NotFoundError
from opensearchpy import connections
import logging

logger = logging.getLogger(__name__)

@registry.register_document
class CoreEbayitemDocument(Document):

    class DoesNotExist(Exception):
        pass  # Define the DoesNotExist exception

    shoe_size_conversion = fields.NestedField(properties={
        'id': fields.IntegerField(),  # Include the 'id' field for the foreign key relationship between data table 'core_ebayitem' and 'core_shoesizeconversion'
        'foot_length_in': fields.FloatField(),
        'us_shoe_size': fields.TextField(),
        'europe_shoe_size': fields.TextField(),
        'uk_shoe_size': fields.TextField(),
        'france_shoe_size': fields.TextField(),
        'japan_shoe_size': fields.TextField(),
        'korea_china_shoe_size': fields.TextField(),
    })

    class Index:
        # Name of the Elasticsearch index
        name = 'core_ebay_items'

        settings = {  # See Opensearch Indices API reference for available settings
            'number_of_shards': 1,
            'number_of_replicas': 0
        }

    class Django:
        model = CoreEbayitem  # The model associated with this Document

        # The fields to be indexed in Elasticsearch/Opensearch
        fields = [
            'featured',
            'id',
            'created_at',
            'gallery_url',
            'title',
            'price',
            'color',
            'size',
            'item_id',
            'item_web_url',
            'availability',
            'itemEndDate',
            'itemCreationDate',
            'categoryId',
            'categoryIdPath',
            'us_shoe_size', # Retaining the direct US shoe size for convenience
            'shoe_size_width',
            'hat_size',
            'chest_size',
            'bra_size',
            'waist_size',
            'inseam',
            'hip_size',
            'waist_to_hem',
            'shoulder_to_shoulder',
            'shoulder_to_hem',
            'women_size',
            'bottoms_size',
            'ring_size',
            'item_length',
            'necklace_length',
            'material',
            'brand',
            'user_id',
            'username',
        ]

    @classmethod
    def generate_id(cls, object_instance):
        """
        Use the item_id as the _id for the document in OpenSearch.
        """
        return object_instance.item_id

    @classmethod
    def prepare(cls, instance):
        """
        Prepare the instance data for indexing in OpenSearch.
        """
        price_str = instance.price

        data = {
            "featured": instance.featured,
            "id": instance.id,
            "created_at": instance.created_at,
            "gallery_url": instance.gallery_url,
            "title": instance.title,
            "price": float(str(price_str).replace('$', '').strip()) if price_str else 0.00,  # Default to 0.00 if None
            "color": instance.color,
            "size": instance.size,
            "item_id": instance.item_id,
            "item_web_url": instance.item_web_url,
            "availability": instance.availability,
            "itemCreationDate": instance.itemCreationDate,
            "itemEndDate": instance.itemEndDate,
            "categoryId": instance.categoryId,
            "categoryIdPath": instance.categoryIdPath,
            "us_shoe_size": instance.us_shoe_size,
            "shoe_size_width": instance.shoe_size_width,
            "hat_size": instance.hat_size,
            "chest_size": instance.chest_size,
            "bra_size": instance.bra_size,
            "waist_size": instance.waist_size,
            "inseam": instance.inseam,
            "hip_size": instance.hip_size,
            "waist_to_hem": instance.waist_to_hem,
            "shoulder_to_shoulder": instance.shoulder_to_shoulder,
            "shoulder_to_hem": instance.shoulder_to_hem,
            "women_size": instance.women_size,
            "bottoms_size": instance.bottoms_size,
            "ring_size": instance.ring_size,
            "item_length": instance.item_length,
            "necklace_length": instance.necklace_length,
            "material": instance.material,
            "brand": instance.brand,
            "user_id": instance.user_id,
            "username": instance.username,
        }

        # Handle the nested shoe_size_conversion field
        if instance.shoe_size_conversion:
            data["shoe_size_conversion"] = {
                "id": instance.shoe_size_conversion.id,
                "foot_length_in": instance.shoe_size_conversion.foot_length_in,
                "us_shoe_size": instance.shoe_size_conversion.us_shoe_size,
                "europe_shoe_size": instance.shoe_size_conversion.europe_shoe_size,
                "uk_shoe_size": instance.shoe_size_conversion.uk_shoe_size,
                "france_shoe_size": instance.shoe_size_conversion.france_shoe_size,
                "japan_shoe_size": instance.shoe_size_conversion.japan_shoe_size,
                "korea_china_shoe_size": instance.shoe_size_conversion.korea_china_shoe_size,
            }
        else:
            pass
        return data

    # SYNCS ALL item_id(s) indexed data with any manual mysql data field changes with the docker opensearch indexed items
    @classmethod
    def create_or_update(cls, item):
        """
        Create or update the document in OpenSearch based on item_id.
        """
        if isinstance(item, dict): # Check if 'item' is a dict or object
            item_id = item['itemId'] # if it's a dictionary, extract item_id
        else:
            item_id = item.item_id 

        logger.debug(f"Processing CoreEbayitem with ID now {item_id}")

        # Get the OpenSearch client
        client = connections.get_connection()

        try:
            # Check if the document with the same item_id exists
            client.get(index=cls._index._name, id=item_id)  # Check if the document exists
            logger.debug(f"Document with ID {item_id} exists. Updating...")
            # Prepare the data for the document
            data = cls.prepare(item)  # Call prepare as a class method
            logger.debug(f"Prepared data: {data}")
            # Update the existing document using the OpenSearch client
            client.update(
                index=cls._index._name,  # Use the index name
                id=item_id,              # Document ID
                body={'doc': data}       # Data to update
            )
            logger.debug(f"Updated CoreEbayitemDocument with ID {item_id}.")
        except NotFoundError:
            # If the document does not exist, create a new one
            logger.debug(f"Document with ID {item_id} does not exist. Creating...")
            data = cls.prepare(item)  # Call prepare as a class method
            client.index(
                index=cls._index._name,  # Use the index name
                id=item_id,             # Document ID
                body=data               # Data to index
            )
            logger.debug(f"Created new CoreEbayitemDocument with ID {item_id}.")
        except Exception as e:
            # Handle other exceptions
            logger.error(f"Error processing CoreEbayitem with ID {item_id}: {e}")

    # SYNCS SINGULAR item_id indexed data with any manual mysql data field changes with the docker opensearch indexed items
    @classmethod
    def sync_item_by_id(cls, item_id): 
        """
        Sync a specific CoreEbayitem to OpenSearch by its item_id.
        """
        try:
            # Fetch the item from the database
            item = CoreEbayitem.objects.get(item_id=item_id)
            logger.debug(f"Found CoreEbayitem with ID {item_id}. Syncing...")

            # Use the existing create_or_update method to sync the item
            cls.create_or_update(item)
            logger.debug(f"Successfully synced CoreEbayitem with ID {item_id}.")
        except CoreEbayitem.DoesNotExist:
            # Handle the case where the item does not exist in the database
            logger.warning(f"CoreEbayitem with ID {item_id} does not exist in the database.")
        except Exception as e:
            # Handle other exceptions
            logger.error(f"Error syncing CoreEbayitem with ID {item_id}: {e}")

    @classmethod
    def delete(cls, instance):

        import logging

        """
        Deletes the CoreEbayitem document and any associated FavoriteItem documents.
        """
        item_id = instance.item_id

        # Delete CoreEbayitemDocument from OpenSearch
        try:
            document = cls.get(id=item_id)
            document.delete()
            logger.info(f"CoreEbayitemDocument with ID {item_id} deleted successfully.")
        except Exception as e:
            logger.error(f"Error deleting CoreEbayitemDocument for item {item_id}: {e}")

        # Delete related FavoriteItem entries from the database
        from .models import FavoriteItem  # Import model here to avoid circular imports
        favorite_items = FavoriteItem.objects.filter(item_id=item_id)
        deleted_count, _ = favorite_items.delete()  # delete() returns a tuple with the count of deleted items
        logger.info(f"Deleted {deleted_count} FavoriteItem(s) from the database with item_id {item_id}.")

        # Delete related FavoriteItemDocument(s) from OpenSearch
        try:
            from .documents import FavoriteItemDocument  # Import document here to avoid circular imports
            favorite_document = FavoriteItemDocument.search().filter("term", item_id=item_id)
            favorite_document.delete()
            logger.info(f"FavoriteItemDocument(s) with item_id {item_id} deleted successfully from OpenSearch.")
        except Exception as e:
            logger.error(f"Error deleting FavoriteItemDocument(s) for item {item_id}: {e}")


@registry.register_document
class FavoriteItemDocument(Document):
    user_id = fields.IntegerField(attr="user_id")  

    class Index:
        name = 'favorite_items'

        settings = {
            'number_of_shards': 1,
            'number_of_replicas': 0
        }

    class Django:
        model = FavoriteItem

        fields = [
            'item_id',
            'is_favorited',
            'favorited_at',
        ]

        # If you want to include related fields, you can define them like this:
        def user_id(self, instance):
            return instance.user_id  # Get the ID of the user

        def username(self, instance):
            return instance.user.username if instance.user else None  # Get the username if user exists 
            
    @classmethod
    def delete(cls, instance):
        """
        Deletes the document corresponding to the given model instance.
        """
        try:
            # Use the item_id or other unique identifier to delete the document
            document = cls.get(id=instance.item_id)  # Assuming item_id is the unique identifier
            document.delete()  # Deletes the document from OpenSearch
            logger.debug(f"Document with ID {instance.item_id} deleted successfully.")
        except Exception as e:
            logger.error(f"Error deleting document for item {instance.item_id}: {e}")
