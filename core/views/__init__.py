"""Views for the core app, grouped by feature area.

Re-exported here so URL configs can keep using ``views.<name>``.
"""
from .pages import (  # noqa: F401
    sitemap_view,
    index,
    about,
    newsletter,
    tos,
    contact,
    capture_email,
)
from .accounts import (  # noqa: F401
    verify_recaptcha,
    signup,
    account_view,
    send_verification_code,
    verify_code,
    account_management,
    profile_view,
    login_user,
    CustomPasswordResetView,
)
from .favorites import (  # noqa: F401
    get_favorite_items,
    check_auth,
    toggle_favorite,
    favorited_items,
)
from .search import (  # noqa: F401
    get_category_group_for_id,
    create_global_size_filters,
    create_category_specific_size_filters,
    create_shoe_size_filter,
    create_generic_size_filter,
    get_curated_filters_config,
    opensearch_results,
    find_item_by_slug,
    browse_view,
)
from .ebay_import import (  # noqa: F401
    convert_image_to_webp,
    save_selected_items,
    display_search_results,
    update_category,
)
from .marketplace import (  # noqa: F401
    get_fashion_service,
    create_listing_view,
    get_category_tree,
    search_categories,
    get_category_breadcrumb,
    select_detected_items,
    MarketplaceItemCreateAPIView,
    MarketplaceItemListAPIView,
    CategoryListAPIView,
    FashionDetectionTestAPIView,
)
from .uploads import (  # noqa: F401
    upload_temp_image,
    create_working_image,
    clear_listing_session,
)
