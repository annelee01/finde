import xml.etree.ElementTree as ET
import requests, urllib.parse, os, json
from django.http import JsonResponse
from difflib import SequenceMatcher
from finde.ebay_search import get_cached_access_token, update_image_url
from django.db import transaction
from django.contrib import messages
from django.db.models import Q
from datetime import datetime, timezone
from django.utils import timezone
from django.conf import settings
from core.decorators import admin_required

def check_item_availability(item_id):
    """Proprietary implementation omitted in this public repository."""
    pass

def check_if_relisted(itemIds):
    """Proprietary implementation omitted in this public repository."""
    pass
OPENSEARCH_URL = os.getenv('OPENSEARCH_URL')
if not OPENSEARCH_URL:
    opensearch_hosts = settings.OPENSEARCH_DSL['default']['hosts']
    if isinstance(opensearch_hosts, str):
        OPENSEARCH_URL = f'http://{opensearch_hosts}'
    else:
        default_host = opensearch_hosts[0]
        scheme = 'https' if settings.OPENSEARCH_DSL['default'].get('use_ssl') else 'http'
        OPENSEARCH_URL = f"{scheme}://{default_host['host']}:{default_host['port']}"

def delete_from_opensearch(item_id):
    """
    Delete an "old" item data from OpenSearch by item_id when an item is relisted with "new" item data

Proprietary implementation omitted in this public repository."""
    pass

@admin_required
def get_ended_items(request):
    """Proprietary implementation omitted in this public repository."""
    pass

@admin_required
def manual_relist(request, item_id=None):
    """Proprietary implementation omitted in this public repository."""
    pass
