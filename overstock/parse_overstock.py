import requests
import re
import json
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from loguru import logger

import requests
import urllib.parse

TEST_LOCAL = True

CUR_DIR = Path(__file__).parent

html_path = CUR_DIR / "overstock_detail_2025-02-10_10-45-52.html"
html_path = CUR_DIR / "overstock_detail_2025-02-10_10-45-54.html"
html_path = CUR_DIR / "overstock_detail_2025-02-10_10-45-57.html"
html_path = CUR_DIR / "overstock_detail_2025-02-10_10-46-01.html"
html_path = CUR_DIR / "overstock_detail_2025-02-10_10-46-02.html"
html_path = CUR_DIR / "overstock_detail_2025-02-10_10-46-06.html"
html_path = CUR_DIR / "overstock_detail_2025-02-10_10-46-08.html"
html_path = CUR_DIR / "overstock_detail_2025-02-10_10-45-45.html"
html_path = CUR_DIR / "overstock_detail_2025-02-10_10-45-49.html"

output_path = CUR_DIR.parent / "result" / "overstock-result.json"


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


def get_reviews(
    api_key: str,
    merchant_id: str,
    page_id: str,
) -> dict[str, Any]:
    ret: dict[str, Any] = {}

    size = 10
    offset = 10 * 0
    url = f"https://display.powerreviews.com/m/{merchant_id}/l/en_US/product/{page_id}/reviews?paging.from={offset}&paging.size={size}&filters=&search=&sort=Newest&image_only=false&page_locale=en_US&_noconfig=true&apikey={api_key}"
    resp = requests.get(url)
    resp_json = resp.json()

    ret["rollup"] = get_from_json(resp_json, ["results", 0, "rollup"])
    ret["reviews"] = list(get_from_json(resp_json, ["results", 0, "reviews"]))

    pages_total = get_from_json(resp_json, ["paging", "pages_total"])
    for i in range(1, pages_total):
        logger.debug(f"fetching review: {i}/{pages_total} page")
        offset = size * i
        url = f"https://display.powerreviews.com/m/{merchant_id}/l/en_US/product/{page_id}/reviews?paging.from={offset}&paging.size={size}&filters=&search=&sort=Newest&image_only=false&page_locale=en_US&_noconfig=true&apikey={api_key}"
        resp = requests.get(url)
        resp_json = resp.json()
        ret["reviews"].extend(list(get_from_json(resp_json, ["results", 0, "reviews"])))
    return ret


def parse_overstock(html_content: str) -> dict[str, Any]:
    page_elem = BeautifulSoup(html_content, "html.parser")
    dict_details: dict[str, Any] = {}

    missing_attrs: dict[str, Any] = {}
    init_data: dict[str, Any] = {}
    datalayer_product: dict[str, Any] = {}
    render_config: dict[str, Any] = {}

    script_elems = page_elem.select("script")
    for script_elem in script_elems:
        if "const missingAttributes" in script_elem.text:
            pattern = re.compile(
                r"const\s+missingAttributes\s*=\s*(\{.*?\})\s*const\s+scripts",
                re.DOTALL,
            )
            matches = pattern.findall(script_elem.string)
            json_text = matches[0]
            missing_attrs = json.loads(json_text)
        if script_elem.attrs.get("id") == "web-pixels-manager-setup":
            pattern = re.compile(
                r"initData:\s*(\{.*?purchasingCompany\"\:null\})\,\}",
                re.DOTALL,
            )
            matches = pattern.findall(script_elem.string)
            json_text = matches[0]
            init_data = json.loads(json_text)
        if "window.salesforce.datalayer.product" in script_elem.text:
            pattern = re.compile(
                r"window.salesforce.datalayer.product\s*=\s*(\{.*?\})\;",
                re.DOTALL,
            )
            matches = pattern.findall(script_elem.string)
            json_text = matches[1]
            datalayer_product = json.loads(json_text)
        if "merchant_group_id" in script_elem.text:
            patterns = {
                "api_key": r'api_key:\s*"([^"]+)"',
                "merchant_id": r'merchant_id:\s*"([^"]+)"',
                "page_id": r'page_id:\s*"([^"]+)"',
            }
            render_config = {key: re.search(pattern, script_elem.string).group(1) for key, pattern in patterns.items()}

    dict_details["success"] = True
    dict_details["url"] = get_from_json(missing_attrs, ["url"])
    dict_details["result_count"] = 1

    detail: dict[str, Any] = {}

    detail["name"] = get_from_json(missing_attrs, ["name"])
    detail["brand"] = get_from_json(missing_attrs, ["brand", "name"])
    detail["url"] = get_from_json(missing_attrs, ["url"])

    # Description
    description: str = get_from_json(missing_attrs, ["description"])
    detail["description"] = description

    detail["asin"] = None  # TODO
    detail["retailer_badge"] = None  # TODO
    detail["deal_badge"] = None  # TODO

    # Listing ID
    product_variants = get_from_json(init_data, ["productVariants"])
    detail["listing_id"] = get_from_json(product_variants, [0, "product", "id"])

    detail["list_price"] = None  # TODO

    # Price
    detail["price"] = get_from_json(product_variants, [0, "price", "amount"])

    detail["price_reduced"] = None  # TODO
    detail["price_per_unit"] = None  # TODO

    # Currency & Symbol
    detail["currency"] = get_from_json(product_variants, [0, "price", "currencyCode"])  # TODO
    detail["currency_symbol"] = get_from_json(datalayer_product, ["currency"])

    detail["buying_offers"] = None  # TODO
    detail["other_sellers"] = None  # TODO

    # Rating
    reviews = get_reviews(
        api_key=get_from_json(render_config, ["api_key"]),
        merchant_id=get_from_json(render_config, ["merchant_id"]),
        page_id=get_from_json(render_config, ["page_id"]),
    )
    detail["rating"] = get_from_json(reviews, ["rollup", "average_rating"])
    detail["total_ratings"] = get_from_json(reviews, ["rollup", "rating_count"])

    detail["past_month_sales"] = None  # TODO
    detail["is_prime"] = None  # TODO
    detail["shipping_info"] = None  # TODO
    detail["delivery_zipcode"] = None  # TODO
    detail["addon_offers"] = None  # TODO
    detail["pay_later_offers"] = None  # TODO

    # Quantity
    detail["max_quantity"] = get_from_json(datalayer_product, ["inventory", 0, "quantity"])

    # Variant
    detail["variant"] = {
        "id": get_from_json(product_variants, [0, "id"]),
    }

    # Categories
    detail["categories"] = get_from_json(datalayer_product, ["taxonomyList"])

    # Main Image
    detail["main_image"] = "https:" + get_from_json(product_variants, [0, "image", "src"])

    # Images
    images: list[str] = []
    image_elems = page_elem.select("li.media-viewer__item")
    for image_elem in image_elems:
        image_elem = image_elem.select_one("img")
        if image_elem is not None:
            image_src = image_elem.attrs.get("data-src", image_elem.attrs.get("src"))
            if image_src is not None:
                image_url = "https:" + image_src
                image_url = image_url.split("?")[0].strip() # Ensures max image size 2000x2000
                images.append(image_url)
    detail["images"] = images

    detail["labelled_images"] = None  # TODO

    # Overview
    attribute_list = get_from_json(datalayer_product, ["attributeList"])
    detail["overview"] = [
        {
            "name": get_from_json(attribute, ["label"]),
            "value": get_from_json(attribute, ["values"]),
        }
        for attribute in attribute_list
    ]

    # Features & Dimensions & Description
    features = []
    dimensions = []
    description_new = ""
    status = "description"
    for line in description.splitlines():
        line = line.strip()
        if line == "":
            continue

        if line.lower() == "features:":
            status = "features"
        elif line.lower() == "dimensions:":
            status = "dimensions"
        elif line.endswith(":"):
            status = "none"
        else:
            if status == "features":
                features.append(line)
            elif status == "dimensions":
                dimensions.append(line)
            elif status == "description":
                description_new += f"{line}\n"
    detail["description"] = description_new
    detail["features"] = features
    detail["dimensions"] = dimensions

    # Details Table
    detail["details_table"] = detail["overview"]

    detail["technical_details"] = None  # TODO
    detail["bestseller_ranks"] = None  # TODO
    detail["seller_name"] = None  # TODO
    detail["seller_url"] = None  # TODO

    # Variants
    detail["variants"] = [
        {
            "price": get_from_json(product_variant, ["price", "amount"]),
            "currency_code": get_from_json(product_variant, ["price", "currencyCode"]),
            "title": get_from_json(product_variant, ["product", "title"]),
            "vendor": get_from_json(product_variant, ["product", "vendor"]),
            "id": get_from_json(product_variant, ["id"]),
            "image": get_from_json(product_variant, ["image", "src"]),
            "sku": get_from_json(product_variant, ["sku"]),
            "variant_title": get_from_json(product_variant, ["title"]),
        }
        for product_variant in product_variants
    ]

    detail["reviews_summary"] = None  # TODO

    # Review Aspects
    detail["review_aspects"] = [
        {
            "name": get_from_json(review, ["details", "nickname"]),
            "headline": get_from_json(review, ["details", "headline"]),
            "comments": get_from_json(review, ["details", "comments"]),
            "rating": get_from_json(review, ["metrics", "rating"]),
            "helpful_votes": get_from_json(review, ["metrics", "helpful_votes"]),
            "not_helpful_votes": get_from_json(review, ["metrics", "not_helpful_votes"]),
            "helpful_score": get_from_json(review, ["metrics", "helpful_score"]),
            "is_staff_reviewer": get_from_json(review, ["badges", "is_staff_reviewer"]),
            "is_verified_buyer": get_from_json(review, ["badges", "is_verified_buyer"]),
            "is_verified_reviewer": get_from_json(review, ["badges", "is_verified_reviewer"]),
        }
        for review in get_from_json(reviews, ["reviews"])
    ]

    # Total Reviews
    detail["total_reviews"] = get_from_json(reviews, ["rollup", "review_count"])

    # Country of Region
    detail["country_of_origin"] = get_from_json(init_data, ["shop", "countryCode"])

    detail["top_reviews"] = None  # TODO
    detail["policy_badges"] = None  # TODO
    detail["product_videos"] = None  # TODO
    detail["product_guides"] = None  # TODO
    detail["warranty_and_support"] = None  # TODO
    detail["from_the_manufacturer"] = None  # TODO
    detail["small_business"] = None  # TODO

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
    list_result = parse_overstock(html_content=html_content)

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

        list_result = parse_overstock(html_content=html_content)

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
