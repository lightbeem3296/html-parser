import base64
import json
import re
import urllib.parse
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup
from loguru import logger

TEST_LOCAL = True

CUR_DIR = Path(__file__).parent

html_path = CUR_DIR / "costco_3.html"
html_path = CUR_DIR / "costco_2.html"
html_path = CUR_DIR / "costco_1.html"
html_path = CUR_DIR / "costco_4.html"

output_path = CUR_DIR.parent / "result" / "costco-result.json"


def get_from_json(json_obj: dict[str, Any] | None, path: list[str] = []) -> Any:
    obj = json_obj
    for key in path:
        if obj is None:
            break
        if isinstance(key, int):
            obj = obj[key]
        elif isinstance(key, str):
            obj = obj.get(key)
    return obj


def parse_costco(html_content: str) -> dict[str, Any]:
    page_elem = BeautifulSoup(html_content, "html.parser")
    dict_details: dict[str, Any] = {}

    script_elems = page_elem.select("script")
    paragraph_elems = page_elem.select("p")

    price = None
    price_listing = None
    product_id = None
    sku = None
    for script_elem in script_elems:
        if "priceMax" in script_elem.text:
            pattern = re.compile(r"priceMax\s*:\s*\'(.*?)\',", re.DOTALL)
            matches = pattern.findall(script_elem.string)
            price = matches[0]

            pattern = re.compile(r"priceMin\s*:\s*\'(.*?)\',", re.DOTALL)
            matches = pattern.findall(script_elem.string)
            price_listing = matches[0]

            pattern = re.compile(r"pid\s*:\s*\'(.*?)\',", re.DOTALL)
            matches = pattern.findall(script_elem.string)
            product_id = matches[0]

            pattern = re.compile(r"sku\s*:\s*\'(.*?)\',", re.DOTALL)
            matches = pattern.findall(script_elem.string)
            sku = matches[0]
            break

    # Success
    dict_details["success"] = True

    # Url
    canonical_elem = page_elem.select_one("link[rel=canonical]")
    dict_details["url"] = canonical_elem.attrs.get("href") if canonical_elem else None

    # Result Count
    dict_details["result_count"] = 1

    detail: dict[str, Any] = {}

    # Name
    name_elem = page_elem.select_one("meta[property='og:title']")
    detail["name"] = name_elem.attrs.get("content") if name_elem else None

    # Brand
    brand_elem = page_elem.select_one("div[itemprop=brand]")
    detail["brand"] = brand_elem.text.strip() if brand_elem else None

    # Url
    detail["url"] = dict_details.get("url")

    # Description
    description_elem = page_elem.select_one("meta[name=description]")
    detail["description"] = description_elem.attrs.get("content") if description_elem else None

    # Product ID
    detail["product_id"] = product_id

    # SKU
    detail["sku"] = sku

    # Model Number
    detail["model_numbers"] = None
    model_numbers = []
    model_number_elems = page_elem.select("div.item-model-number")
    for model_number_elem in model_number_elems:
        span_elem = model_number_elem.select_one("span[itemprop=sku]")
        if span_elem:
            model_numbers.append(span_elem.text.strip())
    detail["model_numbers"] = model_numbers

    # Pills
    detail["pills"] = None
    pills = []
    pills_elem = page_elem.select_one("div.pills-section")
    if pills_elem:
        pill_elems = pills_elem.select("div.single-pill")
        for pill_elem in pill_elems:
            pills.append(pill_elem.text.strip())
    detail["pills"] = pills

    # Image
    image_elem = page_elem.select_one("meta[property='og:image']")
    image_url = image_elem.attrs.get("content")
    detail["main_image"] = image_url.split("?")[0] if image_url else None

    # Images
    images = []
    for script_elem in script_elems:
        if "itemDetailsList" in script_elem.text:
            pattern = re.compile(r"cdn_url:\s*\'(.*?)\',", re.DOTALL)
            matches = pattern.findall(script_elem.string)
            images = matches
            break
    detail["images"] = images

    # Price
    detail["price"] = price
    detail["price_listing"] = price_listing

    # Currency
    detail["currency"] = None
    currenty_elem = page_elem.select_one("span.currency")
    if currenty_elem:
        detail["currency"] = currenty_elem.text.strip()

    # Product Label
    detail["product_label"] = None
    product_label_elem = page_elem.select_one("img[alt='Product Label']")
    if product_label_elem:
        link_elem = product_label_elem.select_one("a")
        if link_elem:
            detail["product_label"] = link_elem.attrs.get("href")

    # Warning
    detail["warning"] = None
    warning_elem = page_elem.select_one("div.prop65warning")
    if warning_elem:
        detail["warning"] = warning_elem.text

    # Includes
    detail["includes"] = None
    for paragraph_elem in paragraph_elems:
        if "Includes:" in paragraph_elem.text:
            includes: list[str] = paragraph_elem.contents[4].text.strip().split(",")
            detail["includes"] = [i.strip() for i in includes]
            break

    # Features
    detail["features"] = None
    features = []
    for paragraph_elem in paragraph_elems:
        if "Features:" in paragraph_elem.text:
            item_list_elem = paragraph_elem.find_next_sibling("ul")
            if item_list_elem:
                item_elems = item_list_elem.select("li")
                for item_elem in item_elems:
                    features.append(item_elem.text.strip())
    detail["features"] = features

    # Demensions & Weight
    detail["dimensions_weight"] = None
    demensions_weight = []
    for paragraph_elem in paragraph_elems:
        if "Dimensions and Weight:" in paragraph_elem.text:
            item_list_elem = paragraph_elem.find_next_sibling("ul")
            if item_list_elem:
                item_elems = item_list_elem.select("li")
                for item_elem in item_elems:
                    demensions_weight.append(item_elem.text.strip())
    detail["dimensions_weight"] = demensions_weight

    # Additional Demensions
    detail["additional_demensions"] = None
    additional_demensions = []
    for paragraph_elem in paragraph_elems:
        if "Additional Dimensions:" in paragraph_elem.text:
            item_list_elem = paragraph_elem.find_next_sibling("ul")
            if item_list_elem:
                item_elems = item_list_elem.select("li")
                for item_elem in item_elems:
                    additional_demensions.append(item_elem.text.strip())
    detail["additional_demensions"] = additional_demensions

    # Specifications
    detail["specifications"] = None
    specifications = {}
    section_title_elems = page_elem.select("h3.section-title")
    for section_title_elem in section_title_elems:
        if "Specifications" in section_title_elem.text:
            item_list_elem = section_title_elem.find_next_sibling("div")
            if item_list_elem:
                item_elems = item_list_elem.select("div.row")
                for item_elem in item_elems:
                    elems = item_elem.select("div")
                    if len(elems) != 2:
                        continue

                    key = elems[0].text.strip()
                    value = elems[1].text.strip()
                    specifications[key] = value
    detail["specifications"] = specifications

    # Manuals & Guides
    detail["manuals_guides"] = None
    manuals = []
    manuals_elem = page_elem.select_one("figure.product-manuals")
    if manuals_elem:
        item_elems = manuals_elem.select("li")
        for item_elem in item_elems:
            if item_elem:
                link_elem = item_elem.select_one("a")
                if link_elem:
                    manuals.append(link_elem.attrs.get("href"))
    detail["manuals_guides"] = manuals

    # Shipping
    detail["shipping"] = ""
    shipping_elem = page_elem.select_one("div.product-info-shipping")
    if shipping_elem:
        for content in shipping_elem.contents:
            if isinstance(content, str):
                shipping = content.strip()
                if shipping:
                    detail["shipping"] += content.strip() + "\n"
            else:
                shipping = content.text.strip()
                if shipping:
                    detail["shipping"] += content.text.strip() + "\n"

    # Returns
    detail["returns"] = ""
    returns_elem = page_elem.select_one("div.product-info-returns")
    if returns_elem:
        for content in returns_elem.contents:
            if isinstance(content, str):
                return_str = content.strip()
                if return_str:
                    detail["returns"] += return_str + "\n"
            else:
                return_str = content.text.strip()
                if return_str:
                    detail["returns"] += return_str + "\n"

    # Reviews
    detail["rating"] = None

    # Total Ratings
    detail["total_ratings"] = None

    # Review Aspects
    detail["review_aspects"] = None

    # Total Reviews
    detail["total_reviews"] = None

    # Variant
    detail["variant"] = None

    # Variant Options

    # Variants
    detail["variant_options"] = None
    detail["variants"] = None

    variant_options: list[dict[str, Any]] = []
    variants: list[dict[str, Any]] = []

    variant_options_data: dict[str, Any] = {}
    variant_data: dict[str, Any] = {}
    for script_elem in script_elems:
        if "var products = [" in script_elem.text:
            pattern = re.compile(r"var\s*products\s*=\s*\[\s*(\[.*?\])\s*\]\;", re.DOTALL)
            matches = pattern.findall(script_elem.string)
            json_text = matches[0]
            variant_data = json.loads(json_text)

            pattern = re.compile(r"var\s*options\s*=\s*\[\s*(\[.*?\])\s*\]\;", re.DOTALL)
            matches = pattern.findall(script_elem.string)
            json_text = matches[0]
            json_text = json_text.replace("'", '"')
            variant_options_data = json.loads(json_text)
            break

    for variant_option in variant_options_data:
        variant_options.append(
            {
                "type": get_from_json(variant_option, ["n"]),
                "values": get_from_json(variant_option, ["v"]),
            }
        )
    detail["variant_options"] = variant_options

    for variant in variant_data:
        price = None
        b64_price = get_from_json(variant, ["price"])
        if b64_price:
            price = base64.b64decode(b64_price).decode("utf-8")
        list_price = None
        b64_list_price = get_from_json(variant, ["listPrice"])
        if b64_list_price:
            list_price = base64.b64decode(b64_list_price).decode("utf-8")
        variants.append(
            {
                "part_number": get_from_json(variant, ["partNumber"]),
                "product_url": get_from_json(variant, ["productUrl"]),
                "price": price,
                "list_price": list_price,
                "min_quantity": get_from_json(variant, ["minQty"]),
                "max_quantity": get_from_json(variant, ["maxQty"]),
                "img_url": get_from_json(variant, ["img_url"]),
                "options": get_from_json(variant, ["options"]),
                "inventory": get_from_json(variant, ["inventory"]),
            }
        )
    detail["variants"] = variants

    dict_details["detail"] = detail
    dict_details["remaining_credits"] = None

    return dict_details


def test_with_api() -> None:
    url = "https://www.bedbathandbeyond.com/Lighting-Ceiling-Fans/13.3-Modern-Matte-Black-3-Light-Crystal-Flush-Mount-Chandelier/36053058/product.html?refccid=6HTD2IHKWJY3Y4SIE5EGK5LLFY&searchidx=0"
    url = "https://www.bedbathandbeyond.com/Home-Garden/Motion-Sensor-13-Gallon-50-Liter-Stainless-Steel-Odorless-Slim-Trash-Can-by-Furniture-of-America/37966526/product.html?refccid=JCHJ6R35HXZ3VHCC6JVZL4PNVA&searchidx=0"
    url = "https://www.bedbathandbeyond.com/Home-Garden/Modern-Sectional-Couch-Comfortable-Upholstered-Sofa-Set-with-Lumbar-Pillow-and-Throw-Pillow-for-Living-Room/41966740/product.html?refccid=RZUUDKKB5PRJ4I2HGWBAMZKWLQ&searchidx=0"
    url = "https://www.bedbathandbeyond.com/Bedding-Bath/Are-You-Kidding-Bare-Coma-Inducer-Oversized-Comforter-Antarctica-Gray/32084702/product.html?refccid=NH4HBGMYILPIHQSANNNRO25RLU&searchidx=0"
    url = "https://www.bedbathandbeyond.com/Home-Garden/Alexander-Home-Megan-Traditional-Area-Rug/32828549/product.html?refccid=SXMGM56V6QZ2472KRRK3BJNXAU&searchidx=0"
    url = "https://www.bedbathandbeyond.com/Lighting-Ceiling-Fans/13.3-Modern-Matte-Black-3-Light-Crystal-Flush-Mount-Chandelier/36053058/product.html?refccid=JPSO3GA7ELHLILSDRK64ZXT73Q&searchidx=1&option=69615223"
    url = "https://www.bedbathandbeyond.com/Bedding-Bath/Are-You-Kidding-Bare-Coma-Inducer-Oversized-Comforter-Antarctica-Gray/32084702/product.html"
    url = "https://www.bedbathandbeyond.com/Home-Garden/Motion-Sensor-13-Gallon-50-Liter-Stainless-Steel-Odorless-Slim-Trash-Can-by-Furniture-of-America/37966526/product.html?refccid=JCHJ6R35HXZ3VHCC6JVZL4PNVA&searchidx=0"

    # encode url
    encoded_url = urllib.parse.quote(url, safe=":/")

    api_url = f"https://unwrangledrf.applikuapp.com/api/unblock?url={encoded_url}&render_js=false&premium_proxy=false&country_code=us&api_key=9b4d3f68caa2f7d103813f746b75e44ebb11749e"

    response = requests.get(api_url)
    html_content = response.text
    list_result = parse_costco(html_content=html_content)

    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(
            list_result,
            output_file,
            ensure_ascii=False,
            default=str,
            indent=2,
        )

    logger.info(f"saved to `{output_path}`")


def test_with_local_files() -> None:
    with html_path.open("r", encoding="utf-8") as html_file:
        html_content = html_file.read()

        list_result = parse_costco(html_content=html_content)

        with output_path.open("w", encoding="utf-8") as output_file:
            json.dump(
                list_result,
                output_file,
                ensure_ascii=False,
                default=str,
                indent=2,
            )

        logger.info(f"saved to `{output_path}`")


def main() -> None:
    if TEST_LOCAL:
        test_with_local_files()
    else:
        test_with_api()


if __name__ == "__main__":
    main()
