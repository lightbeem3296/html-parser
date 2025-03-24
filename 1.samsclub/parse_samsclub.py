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

html_path = CUR_DIR / "samsclub_detail_2025-03-20_13-31-07.html"
html_path = CUR_DIR / "samsclub_detail_2025-03-20_13-31-58.html"
html_path = CUR_DIR / "samsclub_detail_2025-03-20_13-27-54.html"
html_path = CUR_DIR / "samsclub_detail_2025-03-20_13-31-09.html"
html_path = CUR_DIR / "samsclub_detail_2025-03-20_13-30-59.html"
html_path = CUR_DIR / "samsclub_detail_2025-03-24_17-16-48.html"
html_path = CUR_DIR / "samsclub_detail_2025-03-24_17-17-17.html"
html_path = CUR_DIR / "samsclub_detail_2025-03-24_17-17-47.html"

output_path = CUR_DIR.parent / "result" / "samsclub-result.json"


def parse_detail(html_content: str) -> dict[str, Any]:
    def get_from_json(json_obj: dict[str, Any] | None, path: list[str] = []) -> Any:
        obj = json_obj
        for key in path:
            if obj is None:
                break
            if isinstance(key, int):
                if key >= len(obj):
                    break
                obj = obj[key]
            elif isinstance(key, str):
                obj = obj.get(key)
        return obj

    def parse_html_as_str(html_text: str | None) -> str:
        if not html_text:
            return ""

        soup = BeautifulSoup(html_text, "html.parser")
        return soup.get_text()

    def parse_html_as_data(html_text: str | None) -> list:
        ret = []

        if not html_text:
            return ret

        soup = BeautifulSoup(html_text, "html.parser")

        ul_elems = soup.select("ul")
        for ul_elem in ul_elems:
            list_data = []
            li_elems = ul_elem.select("li")
            for li_elem in li_elems:
                list_data.append(li_elem.get_text().strip())
            if list_data:
                ret.append(list_data)

        if not ul_elems:
            list_data = []
            li_items = soup.select("li")
            for li_item in li_items:
                list_data.append(li_item.get_text().strip())
            if list_data:
                ret.append(list_data)

        table_elems = soup.select("table")
        for table_elem in table_elems:
            table_data = {}
            tr_elems = table_elem.select("tr")
            for tr_elem in tr_elems:
                td_elems = tr_elem.select("td")
                if len(td_elems) >= 2:
                    table_data[td_elems[0].get_text().strip()] = td_elems[1].get_text().strip()

            if table_data:
                ret.append(table_data)

        return ret

    page_elem = BeautifulSoup(html_content, "html.parser")
    dict_details: dict[str, Any] = {}

    json_data = {}
    product_data = {}
    image_data = []
    messages_data = []
    script_elem = page_elem.select_one("script#tb-djs-wml-redux-state")
    if script_elem is not None:
        json_data_str = script_elem.text
        json_data: dict = json.loads(json_data_str)

        products_data: dict = json_data.get("cache", {}).get("products", {})
        if products_data:
            product_data = list(products_data.values())[0]

        product_images: dict = json_data.get("productImages", {})
        if product_images:
            image_data = (list(product_images.values())[0]).get("images", [])

        messages_data: list = product_data.get("messages", [])

    # Success
    dict_details["success"] = True

    # Url
    canonical_elem = page_elem.select_one("link[rel=canonical]")
    dict_details["url"] = canonical_elem.attrs.get("href") if canonical_elem else None

    # Result Count
    dict_details["result_count"] = 1

    detail: dict[str, Any] = {}

    # Name
    detail["name"] = get_from_json(product_data, ["descriptors", "name"])

    # Brand
    detail["brand"] = get_from_json(product_data, ["manufacturingInfo", "brand"])

    # Url
    detail["url"] = dict_details.get("url")

    # Highlight
    detail["highlight"] = None
    highlight_text = get_from_json(product_data, ["descriptors", "shortDescription"])
    parsed_data = parse_html_as_data(highlight_text)
    if parsed_data:
        detail["highlight"] = parsed_data[0]

    # Description
    detail["description"] = parse_html_as_str(get_from_json(product_data, ["descriptors", "longDescription"]))

    # Product ID
    detail["product_id"] = get_from_json(product_data, ["productId"])

    # SKU
    detail["sku"] = get_from_json(product_data, ["skus", 0, "skuId"])

    # UPC
    detail["upc"] = get_from_json(product_data, ["skus", 0, "onlineOffer", "generatedUPC"])

    # GTIN
    detail["gtin"] = get_from_json(product_data, ["skus", 0, "onlineOffer", "gtin"])

    # Item Number
    detail["item_number"] = get_from_json(product_data, ["skus", 0, "onlineOffer", "itemNumber"])

    # Model Number
    detail["model_number"] = get_from_json(product_data, ["manufacturingInfo", "model"])

    # Image
    detail["main_image"] = get_from_json(image_data, [0, "ImageUrl"])

    # Images
    detail["images"] = [data.get("ImageUrl") for data in image_data]

    # Price
    detail["price"] = get_from_json(product_data, ["skus", 0, "onlineOffer", "price", "finalPrice", "amount"])
    detail["price_listing"] = get_from_json(product_data, ["skus", 0, "onlineOffer", "price", "startPrice", "amount"])
    detail["price_unit"] = get_from_json(product_data, ["skus", 0, "onlineOffer", "price", "unitPrice", "amount"])

    # Currency
    detail["currency"] = get_from_json(product_data, ["skus", 0, "onlineOffer", "price", "startPrice", "currency"])

    # Demensions & Weight
    detail["dimensions_weight"] = get_from_json(product_data, ["skus", 0, "skuLogistics", "weight"])

    # Additional Demensions
    detail["additional_demensions"] = get_from_json(product_data, ["skus", 0, "skuLogistics"])

    # Specifications
    detail["specifications"] = None
    specifications_text = get_from_json(product_data, ["manufacturingInfo", "specification"])
    parsed_data = parse_html_as_data(specifications_text)
    if parsed_data:
        detail["specifications"] = parsed_data

    # Shipping
    detail["shipping"] = None
    for message in messages_data:
        if message.get("key") == "sidesheet.shipping.upsell.message":
            detail["shipping"] = parse_html_as_str(message.get("message"))
            break

    # Pickup
    detail["pickup"] = None
    for message in messages_data:
        if message.get("key") == "channelbanner.pickup.message":
            detail["pickup"] = parse_html_as_str(message.get("message", ""))
            break

    # Returns
    detail["returns"] = get_from_json(product_data, ["skus", 0, "returnInfo"])

    # Reviews
    detail["rating"] = get_from_json(product_data, ["reviewsAndRatings", "avgRating"])

    # Total Ratings
    detail["total_ratings"] = get_from_json(product_data, ["reviewsAndRatings", "numReviews"])

    # Total Reviews
    detail["total_reviews"] = get_from_json(product_data, ["reviewsAndRatings", "numReviews"])

    # Variant
    detail["variant"] = None

    # Variant Options
    detail["variant_options"] = get_from_json(product_data, ["variantSummary", "variantCriteria"])

    # Variants
    detail["variants"] = get_from_json(product_data, ["variantSummary", "variantInfoMap"])

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
    list_result = parse_detail(html_content=html_content)

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

        list_result = parse_detail(html_content=html_content)

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
