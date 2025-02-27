import json
import re
import ast
from typing import Any
from lxml import html
from bs4 import BeautifulSoup
from pathlib import Path

CUR_DIR = Path(__file__).parent
output_path = CUR_DIR.parent / "result" / "costco-result.json"


def parse_product_data(html_file_path):
    with open(html_file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    response = html.fromstring(html_content)
    page_elem = BeautifulSoup(html_content, "html.parser")

    initial_data: dict[str, Any] = {}
    script_elems = page_elem.select("script")
    for script_elem in script_elems:
        if "initializer.initializeComponent({" in script_elem.text and "\\\"UPC\\\"" in script_elem.text:
            pattern = re.compile(r"\"(\{\\\"app\\\".*?\}\})\",", re.DOTALL)
            matches = pattern.findall(script_elem.string)
            json_str = matches[0]
            json_str = json.loads(f"\"{json_str}\"")
            initial_data = json.loads(json_str)

    detail = {}
    
    # Extract product name
    XPATH_PRODUCT_NAME = '//div[@class="sku-title"]/h1/text()'
    product_name = response.xpath(XPATH_PRODUCT_NAME)
    detail['name'] = product_name[0] if product_name else None

    # Extract brand
    brand = response.xpath('//div[@class="shop-product-title"]//a/text()')
    detail['brand'] = brand[0].strip() if brand else None

    # Extract URL
    detail['url'] = response.xpath('//meta[@property="og:url"]/@content')[0] if response.xpath('//meta[@property="og:url"]/@content') else None
    
    # Extract images
    product_imgs = response.xpath('//img[@draggable="false"]/@src')
    detail['images'] = list(dict.fromkeys([i_src.split(';')[0] for i_src in product_imgs])) if product_imgs else None

    # Extract price
    XPATH_PRODUCT_PRICE = '//div[@class="pricing-price"]//div[@class="priceView-hero-price priceView-customer-price"]/span/text()'
    product_price = response.xpath(XPATH_PRODUCT_PRICE)
    detail['price'] = float(product_price[0].replace('$', '').replace(',', '')) if product_price else None
    detail['currency'] = 'USD'
    detail['currency_symbol'] = '$'
    
    # Extract product ID
    sku_id = re.findall(r"\/(\d+).p", detail['url'])[0] if detail['url'] and re.findall(r"\/(\d+).p", detail['url']) else None
    detail['product_id'] = sku_id

    # Extract rating
    XPATH_PRODUCT_RATING = '//div[contains(@class, "ugc-ratings-reviews")]//span[contains(@class, "ugc-c-review-average")]/text()'
    product_rating = response.xpath(XPATH_PRODUCT_RATING)
    detail['rating'] = float(product_rating[0]) if product_rating else None

    # Extract total reviews
    XPATH_NO_OF_REVIEWS = '//div[contains(@class, "ugc-ratings-reviews")]//span[contains(@class, "c-reviews")]/text()'
    total_reviews = response.xpath(XPATH_NO_OF_REVIEWS)
    detail['total_reviews'] = int(total_reviews[0].replace('(', '').replace(')', '').replace(',', '')) if total_reviews else None

    # Extract in_stock status
    online_button_text = response.xpath('//div[@class="fulfillment-add-to-cart-button"]//button/text()')
    detail['in_stock'] = any("Add to Cart" in text for text in online_button_text)

    # Extract categories
    XPATH_PRODUCT_CATEGORY = '//nav[@class="c-breadcrumbs"]//a[@data-track="Breadcrumb"]'
    product_category_names = response.xpath(XPATH_PRODUCT_CATEGORY + '//text()')
    product_category_urls = response.xpath(XPATH_PRODUCT_CATEGORY + '//@href') 
    detail['categories'] = []
    for i, c in enumerate(product_category_names):
        if i > 0: # skip "Best Buy"
            detail['categories'].append({
                'name': c, 
                'url': product_category_urls[i]
            })
    
    # Extract data from script tags
    scripts = response.xpath('//script[contains(text(), "getInitializer")]/text()')
    detail['description'] = None
    detail['included_items'] = []
    detail['product_features'] = []
    detail['is_energy_star_certified'] = False
    detail['model_no'] = None
    
    for i, script_content in enumerate(scripts):
        if 'componentData' in script_content:
            start_index = script_content.find('{', script_content.find('{') + 1)
            end_index = script_content.rfind('}')

            json_string = script_content[start_index:end_index + 1]
            unescaped_json = ast.literal_eval(f'"{json_string}"')
            data = json.loads(unescaped_json)

            if 'componentData' in data['app']:
                # Use ast.literal_eval to safely evaluate the string
                component_data = data['app']['componentData']

                if component_data['product-description']['shouldRenderComponent']:
                    product_description = component_data['product-description']['description']['longDescription']['parsedHtmlFragments']
                    detail['description'] = ' '.join(fragment['plainText'] for fragment in product_description if 'plainText' in fragment)

                if component_data['whats-included']['shouldRenderComponent']:
                    included_items = [item.get('description') for item in component_data["whats-included"]["includedItems"]]
                    detail['included_items'] = included_items

                model_no = component_data['product-features']['modelNumber']
                detail['model_no'] = model_no

                if component_data['product-features']['shouldRenderComponent']:
                    product_features = [{'name': features['title'], 'value': features['description']} for features in component_data['product-features']['features']]
                    detail['product_features'] = product_features

                if component_data['product-energy-ratings']['shouldRenderComponent']:
                    detail['is_energy_star_certified'] = component_data['product-energy-ratings']['energyRatings']['energyStarCertified']

    # Extract specifications
    specs_script = response.xpath('//script[contains(@id, "shop-specifications")]/text()')
    detail['specifications'] = []
    if len(specs_script) > 0:
        specs_data = json.loads(specs_script[0])
        for category in specs_data['specifications']['categories']:
            detail['specifications'].extend([
                {
                    'type': category['displayName'],
                    'name': c_item['displayName'], 
                    'value': c_item['value']
                } for c_item in category['specifications']
            ])

    # TODO: Add code to extract UPC from the specifications script tag
    # and add it to the detail dictionary as detail['upc']
    detail["upc"] = None
    if "specifications" in initial_data:
        specifications = initial_data["specifications"]
        if "categories" in specifications:
            categories = specifications["categories"]
            if isinstance(categories, list):
                for category in categories:
                    if "specifications" in category:
                        sub_specifications = category["specifications"]
                        if isinstance(sub_specifications, list):
                            for sub_specification in sub_specifications:
                                if sub_specification.get("displayName") == "UPC":
                                    detail["upc"] = sub_specification.get("value")

    detail["initial_data"] = initial_data

    return detail

# Test the function
if __name__ == "__main__":
    result = parse_product_data(str(CUR_DIR / "bestbuy_detail_2025-02-27_16-05-10.html"))
    print(json.dumps(result, indent=2))