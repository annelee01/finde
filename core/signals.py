# signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import CoreEbayitem, FavoriteItem
from .documents import CoreEbayitemDocument, FavoriteItemDocument
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=CoreEbayitem)
def index_core_ebayitem(sender, instance, **kwargs):
    try:
        logger.info(f"Indexing CoreEbayitem: {instance.item_id}")
        CoreEbayitemDocument.create_or_update(instance)
    except Exception as e:
        logger.error(f"Error indexing CoreEbayitem {instance.item_id}: {e}")

@receiver(post_delete, sender=CoreEbayitem)
def delete_core_ebayitem(sender, instance, **kwargs):
    try:
        logger.info(f"Deleting CoreEbayitem: {instance.item_id}")
        CoreEbayitemDocument().delete(instance)
    except Exception as e:
        logger.error(f"Error deleting CoreEbayitem {instance.item_id}: {e}")

@receiver(post_save, sender=FavoriteItem)
def update_favorite_item_index(sender, instance, created, **kwargs):
    try:
        logger.info(f"Updating FavoriteItem: {instance.item_id}")
        FavoriteItemDocument.update_document(instance.item_id, instance.user.id, {
            'item_id': instance.item_id,
            'is_favorited': instance.is_favorited,
            'favorited_at': instance.favorited_at,
        })
    except Exception as e:
        logger.error(f"Error updating FavoriteItem {instance.item_id}: {e}")