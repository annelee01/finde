# creates curl commands for displaying mysql docker database items on browse.html

'''

In terminal, run: 
cd ClothingApp
source venv/bin/activate

LOCAL TERMINAL:
python3 manage.py opensearch_init
python manage.py opensearch document index

RAILWAY TERMINAL:
railway login
railway link
Railway run python manage.py opensearch_init
Railway run python manage.py opensearch document index

'''

from django.core.management.base import BaseCommand
from opensearchpy import OpenSearch
from django.conf import settings

from opensearchpy import OpenSearch

class Command(BaseCommand):
    help = 'Initialize OpenSearch indices for AWS OpenSearch Service'

    def handle(self, *args, **options):
        try:
            # Get the full configuration from settings
            opensearch_config = settings.OPENSEARCH_DSL['default']
            
            # Initialize client with all settings at once
            client = OpenSearch(**opensearch_config)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Connection error: {str(e)}'))
            raise

        # 2. Create indices
        core_ebay_items_mapping = {
            "settings": {
                "index": {
                    "number_of_shards": 1,
                    "number_of_replicas": 1,  
                    "refresh_interval": "1s",
                    "analysis": {
                        "filter": {
                            "english_stemmer": {
                                "type": "stemmer",
                                "language": "english"
                            }
                        },
                        "analyzer": {
                            "english_analyzer": {
                                "filter": ["lowercase", "english_stemmer"],
                                "type": "custom",
                                "tokenizer": "standard"
                            }
                        }
                    }
                }
            },
            "mappings": {
                "properties": {
                    "id": {"type": "integer"},
                    "created_at": {"type": "date"},
                    "availability": {"type": "keyword"},
                    "brand": {"type": "text", "analyzer": "english_analyzer"},
                    "categoryId": {"type": "keyword"},
                    "categoryIdPath": {"type": "text"},
                    "chest_size": {"type": "text"},
                    "color": {"type": "keyword"},
                    "gallery_url": {"type": "text"},
                    "hip_size": {"type": "text"},
                    "item_length": {"type": "text"},
                    "necklace_length": {"type": "text"},
                    "hat_size": {"type": "text"},
                    "itemCreationDate": {"type": "text"},
                    "itemEndDate": {"type": "text"},
                    "item_id": {"type": "keyword"},
                    "item_web_url": {"type": "text"},
                    "material": {"type": "text"},
                    "price": {"type": "double"},
                    "ring_size": {"type": "text"},
                    "shoulder_to_hem": {"type": "text"},
                    "shoulder_to_shoulder": {"type": "text"},
                    "size": {"type": "text"},
                    "title": {"type": "text","analyzer": "english_analyzer"},
                    "us_shoe_size": {"type": "keyword"},
                    "user_id": {"type": "keyword"},
                    "username": {"type": "text"},
                    "waist_size": {"type": "text"},
                    "waist_to_hem": {"type": "text"},
                    "women_size": {"type": "text"},
                    "bottoms_size": {"type": "text"},
                    "shoe_size_width": {"type": "text"},
                    "shoe_size_conversion": {
                        "type": "nested",
                        "properties": {
                            "id": {"type": "integer"},
                            "foot_length_in": {"type": "float"},
                            "us_shoe_size": {"type": "text"},
                            "europe_shoe_size": {"type": "text"},
                            "uk_shoe_size": {"type": "text"},
                            "france_shoe_size": {"type": "text"},
                            "japan_shoe_size": {"type": "text"},
                            "korea_china_shoe_size": {"type": "text"}
                        }
                    }
                }
            }
        }

        # Create favorite_items index
        favorite_items_mapping = {
            "settings": {
                "index": {
                    "number_of_shards": 1, 
                    "number_of_replicas": 1, 
                }
            },
            "mappings": {
                "properties": {
                    "user_id": {"type": "keyword"},
                    "item_id": {"type": "keyword"},
                    "is_favorited": {"type": "boolean"},
                    "favorited_at": {"type": "date"}
                }
            }
        }

        # Now create the indices dictionary
        indices = {
            'core_ebay_items': core_ebay_items_mapping,
            'favorite_items': favorite_items_mapping
        }

        for index_name, body in indices.items():
            try:
                # Delete existing index if it exists
                if client.indices.exists(index=index_name):
                    client.indices.delete(index=index_name)
                    self.stdout.write(self.style.WARNING(f'Deleted existing index: {index_name}'))
                
                # Create new index
                client.indices.create(index=index_name, body=body)
                self.stdout.write(self.style.SUCCESS(f'Successfully created index: {index_name}'))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error processing index {index_name}: {str(e)}'))
                raise
