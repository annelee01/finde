from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

@register.simple_tag
def ebay_affiliate_link(item_id):
    campaign_id = '5338008543' # 'Detault campaign' ID from my ebay partner network account
    base_url = 'https://www.ebay.com/itm/'

    affiliate_link = f'{base_url}{item_id}?campid={campaign_id}'
    return affiliate_link

@register.simple_tag
def my_url(value, field_name, urlencode=None):
    url = '?{}={}'.format(field_name, value)

    if urlencode:
        querystring = urlencode.split('&')
        filtered_querystring = filter(lambda p: p.split('=')[0] != field_name, querystring)
        encoded_querystring = '&'.join(filtered_querystring)
        
        # Remove leading '&' if there are parameters left after filtering
        if encoded_querystring:
            url = '{}&{}'.format(url, encoded_querystring)
        else:
            url = url  # No need to add '&' if there are no parameters left

    return url

# Display size button category groupings on browse.html size menu
@register.filter(name='get_display_name')
def get_display_name(dictionary, key):
    """Safely get the value from a dictionary with a fallback to the key itself."""
    return dictionary.get(key, key)

@register.filter
def in_list(value, arg):
    """
    Custom filter to check if a value is in a comma-separated list.
    Usage: {{ value|in_list:"item1,item2,item3" }}
    """
    return value in arg.split(',')

@register.filter
def get_item(dictionary, key):
    """
    Custom filter to get a value from a dictionary using a key.
    Usage: {{ dictionary|get_item:key }}
    """
    return dictionary.get(key, '')


# Converts tags from decimal to fraction for display purposes. Using JS for tags (for dynamic page loading), and using a separate fraction django filter for the size buttons
FRACTION_LABELS = {
    0.5: "1/2",
    0.25: "1/4",
    0.375: "3/8",
    0.33: "1/3",
    0.75: "3/4",
    0.66: "2/3",
    0.625: "5/8",
    0.875: "7/8",
}


@register.filter
def decimal_to_fraction(size):
    """
    Convert a decimal size (as a string) to a fraction string with superscript.
    Example: "20.5" -> "20 <sup>1/2</sup>"

    Input is escaped; only the generated <sup> markup is marked safe.
    """
    try:
        # Remove quotes and other non-numeric characters
        size = size.replace('"', '').replace("&quot;", "")

        # Check if the size is a numeric string (e.g., "28.5")
        if size.replace(".", "").isdigit():
            decimal_value = float(size)
            integer_part = int(decimal_value)
            fraction = FRACTION_LABELS.get(decimal_value - integer_part)
            if fraction:
                return mark_safe(f"{integer_part} <sup>{fraction}</sup>")
        # Non-numeric sizes (e.g., "S", "M") or uncommon fractions are shown as-is
        return escape(size)
    except (ValueError, TypeError, AttributeError):
        return escape(size)


@register.filter
def get_shoe_width_label(size):
    width_labels = {
        "XXS": "Super Narrow",
        "XS": "Extra Narrow",
        "S": "Narrow",
        "W": "Wide",
        "XW": "Extra Wide",
        "XXW": "Triple Wide",
    }
    return width_labels.get(size, size)