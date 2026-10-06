from django.urls import path
from . import views

from finde.find_relistedItemId import get_ended_items, manual_relist
from .utils import delete_selected_items, update_availability_status_view

from django.conf import settings
from django.conf.urls.static import static



app_name = 'core'

urlpatterns = [
    path('', views.index, name='index'),
    path('contact/', views.contact, name='contact'),
    path('about/', views.about, name='about'),
    path('newsletter/', views.newsletter, name='newsletter'),
    path('tos/', views.tos, name='tos'),
    path('signup/', views.signup, name='signup'),
    path('save-items/', views.save_selected_items, name='save_items'),
    path('delete-items/', delete_selected_items, name='delete_items'),
    path('opensearch_results/', views.opensearch_results, name='opensearch_results'),
    path('browse/', views.browse_view, name='browse'),
    path('browse/<str:item_slug>/', views.browse_view, name='browse_pdp'),     # PDP URLs - this must come AFTTER the regular browse pattern
    path('update-availability/', update_availability_status_view, name='update_availability'),
    path('get-ended-items/', get_ended_items, name='get_ended_items'),
    path('manual-relist/', manual_relist, name='manual_relist'),
    path('update_category/', views.update_category, name='update_category'),
    path('account/', views.account_view, name='account'),
    path('account/login/', views.login_user, name='login'),
    path('account/verify/', views.verify_code, name='verify_code'),
    path('account/edit-profile', views.account_view, name='account_edit-profile'),
    path('account/management/', views.account_management, name='account_management'),
    path('api/favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('api/favorite-items/', views.favorited_items, name='favorited_items'),
    path('api/check-auth/', views.check_auth, name='check_auth'),
    path('capture-email/', views.capture_email, name='capture_email'),
    path('sitemap.xml', views.sitemap_view, name='sitemap'),

    # Add marketplace URLs
    path('listings/create_item/', views.create_listing_view, name='create_listing'),
    path('listings/select_items/', views.select_detected_items, name='select_items'),
    
    # API endpoints
    path('api/marketplace/items/', views.MarketplaceItemCreateAPIView.as_view(), name='api_create_item'),
    path('api/marketplace/items/list/', views.MarketplaceItemListAPIView.as_view(), name='api_list_items'),
    path('api/marketplace/categories/', views.CategoryListAPIView.as_view(), name='api_list_categories'),
    path('api/test-fashion-detection/', views.FashionDetectionTestAPIView.as_view(), name='test-fashion-detection'),
    
    # Image management endpoints (create listing)
    path('api/upload-temp-image/', views.upload_temp_image, name='upload_temp_image'),
    path('api/clear-listing-session/', views.clear_listing_session, name='clear_listing_session'),
    path('api/categories/breadcrumb/', views.get_category_breadcrumb, name='category_breadcrumb'),
    path('api/categories/tree/', views.get_category_tree, name='category_tree'),
    path('api/categories/search/', views.search_categories, name='search_categories'),

    # dynamic pattern paths need to be ordered/rendered last
    path('<str:username>/', views.profile_view, name='profile_detail'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)