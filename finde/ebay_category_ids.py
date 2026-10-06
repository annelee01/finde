# run this file to get a refresh of the ebay category ID data hierarchy. it creates the file 'ebay_category_ids.json'

import requests, settings
from ebay_search import get_cached_access_token
import json

def get_category_hierarchy(category_id, access_token, depth=0, category_path=""):
    # NOTE IMPORTNT ****** the 'url' should ALWAYS be a PRODUCTION url, never SANDBOX
    url = 'https://api.ebay.com/commerce/taxonomy/v1/category_tree/0/get_category_subtree'
    params = {
        'category_id': category_id,
    }

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    response = requests.get(url, params=params, headers=headers)

    categories = []

    if response.status_code == 200:
        data = response.json()
        print("API Data:", data)  
        if 'categorySubtreeNode' in data:
            category_info = data['categorySubtreeNode']['category']
            category_data = {'categoryId': category_info['categoryId'], 'categoryName': category_info['categoryName'], 'depth': depth, 'categoryIdPath': category_path}
            categories.append(category_data)
            if 'childCategoryTreeNodes' in data['categorySubtreeNode']:
                for category in data['categorySubtreeNode']['childCategoryTreeNodes']:
                    sub_category_id = category['category']['categoryId']
                    sub_category_path = f"{category_path}|{sub_category_id}" if category_path else sub_category_id
                    subcategories = get_category_hierarchy(sub_category_id, access_token, depth + 1, sub_category_path)
                    categories.extend(subcategories)
    else:
        print(f"Failed to retrieve categories for category ID {category_id}. Error:", response.text)

    return categories

def update_json_with_category_data(categories):
    # Write the categories data to a JSON file
    with open('ebay_category_ids.json', 'w') as json_file:
        json.dump(categories, json_file)
        print('Updated ebay_category_ids.json file')

def main():
    # Get eBay credentials directly from settings 
    ebay_credentials = settings.EBAY_CREDENTIALS
    client_id = ebay_credentials.get('appid')
    client_secret = ebay_credentials.get('certid')
    ebay_env=settings.EBAY_ENV

    access_token = get_cached_access_token(client_id, client_secret, ebay_env)
    
    # IMPORTANT: Define the top-level category IDs to retrieve from ebay. These are the categories pulled into the app for display
    top_category_ids = [
        '74976', # Women's Vintage Shoes
        '182047', # Women's Vintage Clothing
        '182059', # Vintage Accessories
        '262024',# Vintage & Antique Jewelry
        '260010', # Women's Clothing, Shoes & Accessories (modern)
        '281', # Jewelry & Watches (modern)
        ] 

    categories = []
    # Call the function to get the category hierarchy for each top-level category
    for category_id in top_category_ids:
        categories.extend(get_category_hierarchy(category_id, access_token))
    
    # Update the JSON file with category data
    update_json_with_category_data(categories)

if __name__ == "__main__":
    main()

