import json
from datetime import datetime
import re
from bs4 import BeautifulSoup

from collections import OrderedDict

from utils.parsers import parse_money

def parse_detail(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    detail = {}
    
    # Name
    product_name = soup.select_one('h1[itemprop="name"]')
    detail['name'] = product_name.get_text(strip=True) if product_name else None
    
    # Extract JSON data from script tags
    script_tags = soup.find_all('script', type='application/ld+json')
    json_data_list = [json.loads(tag.string) for tag in script_tags]
    
    # Brand
    detail['brand'] = json_data_list[0]['brand']['name'] if json_data_list and isinstance(json_data_list[0], dict) and 'brand' in json_data_list[0] and isinstance(json_data_list[0]['brand'], dict) else None
    
    # URL
    canonical_link = soup.find('link', rel='canonical')
    detail['url'] = canonical_link['href']
    
    # Categories
    detail['categories'] = [
        {'name': link.get_text(strip=True), 'url': f"https://www.walmart.com{link['href']}"} 
        for link in soup.select('ol.w_4HBV li a')
    ]
    
    # Images
    detail['images'] = [img['src'].split('?')[0] for img in soup.select('div[data-testid="media-thumbnail"] img')]
    
    # Price
    price_element = soup.select_one('span[itemprop="price"]') or soup.select_one('span.w_iUH7')
    if price_element:
        price_text = price_element.get_text(strip=True).split()
        price = price_text[-1] if price_text else None
    else:
        price = None
    detail['price'], detail['currency'], detail['currency_symbol'] = parse_money(price) if price else (None, None, None)

    detail['is_subscription'] = False
    if price and 'month' in price:
        detail['is_subscription'] = True

    # Get offer text like "for 36 months, 0% APR"
    offer_text_element = soup.select_one('div[data-testid="postpaid-price"] div.mid-gray span.mr2')
    detail['offer_text'] = offer_text_element.get_text(strip=True) if offer_text_element else None
    
    # Rating
    detail['rating'] = json_data_list[0].get('aggregateRating', {}).get('ratingValue')
    
    # Total Ratings
    detail['total_ratings'] = json_data_list[0].get('aggregateRating', {}).get('ratingCount')

    detail['total_reviews'] = json_data_list[0].get('aggregateRating', {}).get('reviewCount')
    
    # Top Reviews
    detail['top_reviews'] = []
    for review in json_data_list[0].get('review', []):
        detail['top_reviews'].append({
            'review_title': review.get('name'),
            'review_text': review.get('reviewBody'),
            'rating': review.get('reviewRating', {}).get('ratingValue'),
            'date': datetime.strptime(review.get('datePublished'), '%B %d, %Y').strftime('%Y-%m-%d') if review.get('datePublished') else None,
            'reviewer_name': review.get('author', {}).get('name')
        })
    
    # Specifications, Warnings, Variants
    script_tags = soup.find_all('script', id='__NEXT_DATA__')
    json_data_list = [json.loads(tag.string) for tag in script_tags]

    idml_data = json_data_list[0]['props']['pageProps']['initialData']['data']['idml']
    keys_to_drop = ['arExperience', 'genAiDetails', 'chokingHazards', 'esrbRating', 'mpaaRating', 'product360ImageContainer', 'hasMarketingDescription', 'sizeChart', 'longDescription', 'shortDescription']
    for key, value in idml_data.items():
        if key not in keys_to_drop:
            new_key = re.sub(r'(?<!^)(?=[A-Z])', '_', key).lower()
            if new_key == 'nutrition_facts' and isinstance(value, dict):
                nutrition_facts = value
                structured_nutrition_facts = {
                    "calorie_info": nutrition_facts.get("calorieInfo"),
                    "key_nutrients": nutrition_facts.get("keyNutrients"),
                    "vitamin_minerals": nutrition_facts.get("vitaminMinerals"),
                    "serving_info": nutrition_facts.get("servingInfo"),
                    "additional_disclaimer": nutrition_facts.get("additionalDisclaimer"),
                    "static_content": nutrition_facts.get("staticContent")
                }
                detail[new_key] = structured_nutrition_facts
                
                # Convert camelCase keys to snake_case recursively
                def camel_to_snake(obj):
                    if isinstance(obj, dict):
                        return {re.sub(r'(?<!^)(?=[A-Z])', '_', k).lower(): camel_to_snake(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [camel_to_snake(elem) for elem in obj]
                    else:
                        return obj
                
                detail[new_key] = camel_to_snake(structured_nutrition_facts)
                
            elif new_key == 'product_highlights' and isinstance(value, list):
                for highlight in value:
                    highlight.pop('iconURL', None)
            else:
                detail[new_key] = value
    
    product_data = json_data_list[0]['props']['pageProps']['initialData']['data']['product']
    
    # Seller Information
    detail['seller_name'] = product_data.get('sellerName', '')
    detail['seller_url'] = f"https://www.walmart.com/seller/{product_data.get('sellerId', '')}"
    
    # Returns Information
    
    # two_day_shipping = product_data.get('offerList', [{}])[0].get('shippingOptions', {}).get('twoDayShippingEligible')
    # detail['returns']['two_day_shipping'] = two_day_shipping

    # Estimated Delivery Date
    fulfillment_summary = json_data_list[0]['props']['pageProps']['initialData']['data']['product'].get('fulfillmentSummary')
    delivery_date = fulfillment_summary[0]['deliveryDate'] if fulfillment_summary else None
    detail['est_delivery_date'] = delivery_date.split('T')[0] if delivery_date else None
    
    return_policy_text = json_data_list[0]['props']['pageProps']['initialData']['data']['product']['returnPolicy'].get('returnPolicyText')
    detail['returns_info'] = return_policy_text
    
    # Product ID
    detail['id'] = product_data.get('usItemId')
    
    # Availability
    detail['in_stock'] = json_data_list[0]['props']['pageProps']['initialData']['data']['product']['availabilityStatus'] == "IN_STOCK"

    # Short Description
    detail['description'] = json_data_list[0]['props']['pageProps']['initialData']['data']['idml']['shortDescription']
    
    # Long/Short Description
    long_description_html = json_data_list[0]['props']['pageProps']['initialData']['data']['idml']['longDescription']
    soup_long_description = BeautifulSoup(long_description_html, 'html.parser')
    
    # Check if the long description contains a list
    if soup_long_description.find('ul'):
        long_description = [li.get_text(strip=True) for li in soup_long_description.find_all('li')]
    else:
        long_description = soup_long_description.get_text(strip=True)
    
    detail['key_features'] = long_description

    key_order = [
        'id', 'name', 'brand', 'url', 'images', 'price', 'currency', 'currency_symbol', 'is_subscription', 'offer_text',
        'rating', 'total_ratings', 'total_reviews', 'in_stock', 'categories', 'description', 'key_features', 'seller_name', 'seller_url', 'est_delivery_date', 'returns_info'
    ]

    def get_key_index(key):
        try:
            return key_order.index(key)
        except ValueError:
            return len(key_order)  # Put any keys not in the list at the end

# Sort the detail dictionary based on the key order
    sorted_detail = OrderedDict(sorted(detail.items(), key=lambda x: get_key_index(x[0])))
    
    return sorted_detail




with open('walmart_detail.html', 'r') as file:
    html_content = file.read()

detail = parse_detail(html_content)

print(detail)



