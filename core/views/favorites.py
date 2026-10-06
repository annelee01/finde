"""Saving and listing a user's favorite items."""

import json

from django.contrib.auth.decorators import login_required
from django.db.models import OuterRef, Subquery
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_http_methods

from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..documents import FavoriteItemDocument
from ..models import CoreEbayitem, FavoriteItem


def get_favorite_items(user):
    # Get the subquery to fetch the favorited_at value from FavoriteItem
    favorite_subquery = FavoriteItem.objects.filter(
        user=user,
        item_id=OuterRef('item_id'),  # Match item_id in both models
        is_favorited=True
    ).values('favorited_at')[:1]  # Get the favorited_at field

    # Fetch the actual items based on the item IDs and annotate with favorited_at
    return CoreEbayitem.objects.filter(
        item_id__in=FavoriteItem.objects.filter(user=user, is_favorited=True).values('item_id')
    ).annotate(favorited_at=Subquery(favorite_subquery)).order_by('-favorited_at')

# check authentication to trigger add favorite after login
def check_auth(request):
    if request.user.is_authenticated:
        return JsonResponse({'status': 'authenticated'})
    else:
        return JsonResponse({'status': 'unauthenticated'}, status=401)

@require_http_methods(["POST", "DELETE"])
@login_required
def toggle_favorite(request):
    try:
        if request.method == 'POST':
            data = json.loads(request.body)
            item_id = data.get('item_id')
            is_favorited = data.get('is_favorited')
            favorited_at_str = data.get('favorited_at')
            action = data.get('action')  # Get the action parameter
            favorited_at = parse_datetime(favorited_at_str) if favorited_at_str else timezone.now()

            if not item_id or is_favorited is None or action is None:
                return HttpResponseBadRequest('Missing item_id, is_favorited, or action')

            user = request.user

            if not user.is_authenticated:
                return JsonResponse({'error': 'User not authenticated'}, status=401)

            # Add or update the favorite item in opensearch index data
            if action == 'add':
                favorite_item, created = FavoriteItem.objects.get_or_create(
                    user=user,
                    item_id=item_id,
                    defaults={
                        'is_favorited': is_favorited,
                        'favorited_at': favorited_at
                    }
                )

                if created:
                    favorite_item.is_favorited = is_favorited
                    favorite_item.favorited_at = favorited_at
                    favorite_item.save()

                return JsonResponse({'status': 'success', 'action': 'added'})

            # Remove the favorite item from opensearch data
            if action == 'remove':
                try:
                    favorite_item = FavoriteItem.objects.get(user=user, item_id=item_id)
                    favorite_item.delete()
                    FavoriteItemDocument.delete(favorite_item)
                    return JsonResponse({'status': 'success', 'deleted': True, 'action': 'removed'})
                except FavoriteItem.DoesNotExist:
                    return JsonResponse({'error': 'Item not found in favorites'}, status=404)

        # Remove the favorite item from mysql data
        elif request.method == 'DELETE':
            data = json.loads(request.body)
            item_id = data.get('item_id')

            if not item_id:
                return HttpResponseBadRequest('Missing item_id')

            user = request.user

            # Remove the favorite item
            try:
                favorite_item = FavoriteItem.objects.get(user=user, item_id=item_id)
                favorite_item.delete()
                return JsonResponse({'status': 'success', 'deleted': True})
            except FavoriteItem.DoesNotExist:
                return JsonResponse({'error': 'Item not found in favorites'}, status=404)

    except json.JSONDecodeError:
        return HttpResponseBadRequest('Invalid JSON')
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

    return HttpResponseBadRequest('Invalid request method')

@api_view(['GET'])
def favorited_items(request):
    user = request.user
    if user.is_authenticated:
        # Use the helper function to get the favorite items
        favorited_items = get_favorite_items(user)
        favorited_item_ids = list(favorited_items.values_list('item_id', flat=True))
    else:
        favorited_item_ids = []

    data = {
        'favoritedItemIds': favorited_item_ids,
    }

    return Response(data)
