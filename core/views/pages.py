"""Static pages, home page, sitemap and newsletter capture."""

from urllib.parse import quote_plus

from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render, redirect

from ..curated_filters import CURATED_FILTERS
from ..models import CoreEbayitem, EmailCapture


def sitemap_view(request):
    sitemap_content = '''<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://finde.clothing/</loc>
        <lastmod>2025-01-07</lastmod>
        <changefreq>weekly</changefreq>
        <priority>1.0</priority>
    </url>
    <url>
        <loc>https://finde.clothing/browse/</loc>
        <lastmod>2025-01-07</lastmod>
        <changefreq>daily</changefreq>
        <priority>0.9</priority>
    </url>
    </urlset>'''
    return HttpResponse(sitemap_content, content_type='application/xml')

def index(request):
    # Get only items marked as featured
    featured_items = CoreEbayitem.objects.filter(featured=True).order_by('-created_at')[:4]  # Get up to 4 featured items

    # Get designer filter configuration from CURATED_FILTERS
    designer_filter = CURATED_FILTERS.get('designer', {})
    designer_brands = designer_filter.get('brands', [])

    # Create Q objects for brand matching (case-insensitive)
    brand_queries = Q()
    for brand in designer_brands:
        brand_queries |= Q(brand__icontains=brand)

    # Get designer items
    designer_items = CoreEbayitem.objects.filter(
        brand_queries,
        availability='IN_STOCK'  # Only available items
    ).order_by('-created_at')[:4]  # Get up to 4 designer items

    # Get under the radar items (under $100)
    under_radar_items = CoreEbayitem.objects.filter(
        price__lt=100,  # Less than $100
        availability='IN_STOCK'  # Only available items
    ).order_by('-created_at')[:4]  # Get up to 4 under the radar items

    # Function to format items for template
    def format_items_for_template(items):
        items_data = []
        for item in items:
            # Determine size display
            size_display = 'Unmarked Size'
            if item.size and item.size != 'None':
                size_display = item.size
            elif item.us_shoe_size and item.us_shoe_size != 'None':
                size_display = f"US {item.us_shoe_size}"
                if item.shoe_size_width and item.shoe_size_width != 'None':
                    width_labels = {
                        "XXS": "Super Narrow",
                        "XS": "Extra Narrow",
                        "S": "Narrow",
                        "W": "Wide",
                        "XW": "Extra Wide",
                        "XXW": "Triple Wide",
                    }
                    width_label = width_labels.get(item.shoe_size_width, item.shoe_size_width)
                    size_display += f" {width_label}"
            elif item.bottoms_size and item.bottoms_size != 'None':
                size_display = item.bottoms_size
            elif item.bra_size and item.bra_size != 'None':
                size_display = item.bra_size
            elif item.hat_size and item.hat_size != 'None':
                size_display = item.hat_size
            elif item.ring_size and item.ring_size != 'None':
                size_display = f"Ring Size {item.ring_size}"

            items_data.append({
                'title': item.title,
                'gallery_url': item.gallery_url,
                'price': item.price,
                'brand': item.brand or 'Vintage',
                'size': size_display,
                'item_web_url': item.item_web_url,
                'item_id': item.id,
                'slug': item.gallery_url.replace('.webp', '').replace('webp_images/', ''),
                'availability': item.availability,
            })
        return items_data

    # Format both sets of items
    featured_items_data = format_items_for_template(featured_items)
    designer_items_data = format_items_for_template(designer_items)
    under_radar_items_data = format_items_for_template(under_radar_items)

    # Construct the designer filter URL with all brands exactly as the browse page expects
    # Join all brands with spaces (this matches how the browse page constructs the query)
    brands_query = ' '.join(designer_brands)
    # Manually construct the URL to match the expected format
    designer_filter_url = f'/browse/?page=1&sort_by=newlyAdded&query={quote_plus(brands_query)}&curated_filter=designer'

    # Construct the under the radar filter URL
    under_radar_filter_url = '/browse/?page=1&sort_by=newlyAdded&max_price=100'

    context = {
        'featured_items': featured_items_data,
        'designer_items': designer_items_data,
        'designer_filter_url': designer_filter_url,
        'under_radar_items': under_radar_items_data,
        'under_radar_filter_url': under_radar_filter_url,
        'curated_filters': CURATED_FILTERS,
    }

    return render(request, 'core/index.html', context)

def about(request):
    return render(request, 'core/about.html')

def newsletter(request):
    return render(request, 'core/newsletter.html')

def tos(request):
    return render(request, 'core/tos.html')

def contact(request):
    return render(request, 'core/contact.html')

def capture_email(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        newsletter_trend = request.POST.get('newsletter_trend') == 'yes'

        # Check if the email already exists FIRST
        if EmailCapture.objects.filter(email=email).exists():
            messages.warning(request, "This email is already subscribed.")
        else:
            # Create a new EmailCapture instance ONLY ONCE with both fields
            EmailCapture.objects.create(
                email=email,
                newsletter_trend=newsletter_trend
            )
            messages.success(request, "Thank you for subscribing!")

        return redirect(request.META.get('HTTP_REFERER', '/'))

    return redirect('core:browse')  # Redirect if accessed without POST
