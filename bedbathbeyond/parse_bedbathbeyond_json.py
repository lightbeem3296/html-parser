import json
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from loguru import logger

import requests
import urllib.parse

CUR_DIR = Path(__file__).parent

html_path = CUR_DIR / "123.html"
html_path = CUR_DIR / "bedbathbeyond_detail_2024-12-18_13-40-11.html"
html_path = CUR_DIR / "bedbathbeyond_detail_2024-12-18_16-25-41.html"
html_path = CUR_DIR / "bedbathbeyond_detail_2024-12-18_16-27-21.html"
html_path = CUR_DIR / "bedbathbeyond_detail_2024-12-18_16-27-40.html"
html_path = CUR_DIR / "bedbathbeyond_detail_2024-12-18_16-28-22.html"

output_path = CUR_DIR.parent / "result" / "bedbathbeyond-result.json"


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


def parse_bedbathbeyond(html_content: str) -> list[dict[str, Any]]:
    """Parses html content and returns a list of product information."""

    page_elem = BeautifulSoup(html_content, "html.parser")
    dict_details: dict[str, Any] = {}

    # Extract __NEXT_DATA__ from html
    json_data_str = page_elem.select_one("script[id=__NEXT_DATA__]").text
    json_data = json.loads(json_data_str)

    page_props_data = get_from_json(json_data, ["props", "pageProps"])
    meta_data = get_from_json(page_props_data, ["meta"])
    data_layer_data = get_from_json(meta_data, ["dataLayer"])
    product_data = get_from_json(page_props_data, ["product"])
    config_data = get_from_json(page_props_data, ["config"])

    # Fill result dictionary
    dict_details["success"] = True
    dict_details["url"] = get_from_json(product_data, ["meta", "htmlUrl"])
    dict_details["result_count"] = 1

    # Fill detail
    detail: dict[str, Any] = {}

    detail["name"] = get_from_json(product_data, ["name"])
    detail["brand"] = get_from_json(product_data, ["brandName"])
    detail["url"] = get_from_json(product_data, ["meta", "htmlUrl"])
    detail["description"] = get_from_json(product_data, ["jsonLdDescription"])
    detail["asin"] = None  # TODO
    detail["retailer_badge"] = get_from_json(product_data, ["urgencyMessage"])
    detail["deal_badge"] = None  # TODO
    detail["listing_id"] = get_from_json(product_data, ["id"])

    variant_option_id = get_from_json(product_data, ["defaultOptionId"])
    list_price = None
    for variant in get_from_json(product_data, ["options"]):
        if get_from_json(variant, ["optionId"]) == variant_option_id:
            list_price = get_from_json(variant, ["comparePrice"])
    detail["list_price"] = list_price

    detail["price"] = get_from_json(product_data, ["memberPrice"])
    detail["price_reduced"] = None  # TODO
    detail["price_per_unit"] = None  # TODO
    detail["currency"] = get_from_json(data_layer_data, ["order_currency"])
    detail["currency_symbol"] = get_from_json(product_data, ["priceSet", 0, "symbol"])

    finnancing_offers = get_from_json(page_props_data, ["financingOffer"])
    buying_offers = []
    for offer in finnancing_offers:
        offer_description = None
        description_html = get_from_json(offer, ["html", "messageHtml"])
        if description_html is not None:
            offer_description = BeautifulSoup(
                description_html, "html.parser"
            ).text.strip()
        buying_offers.append(
            {
                "offer_type": get_from_json(offer, ["data", "financingOfferType"]),
                "offer_description": offer_description,
                "price": None,
                "seller": None,
            }
        )
    detail["buying_offers"] = buying_offers

    detail["other_sellers"] = []  # TODO

    ratings: dict[str, int] = get_from_json(product_data, ["ratingCounts"])
    total_point = 0
    total_count = 0
    for key, value in ratings.items():
        total_point += int(key) * value
        total_count += value
    detail["rating"] = total_point / total_count if total_count > 0 else 0
    detail["total_ratings"] = total_count

    detail["past_month_sales"] = None  # TODO
    detail["is_prime"] = None  # TODO
    detail["shipping_info"] = get_from_json(config_data, ["shipping"])
    detail["delivery_zipcode"] = get_from_json(meta_data, ["zipCode"])

    btns_marketing: dict[str, Any] = get_from_json(
        page_props_data,
        ["extendResponse", "marketing", "adh", "offerTypeModal", "buttonsMarketing"],
    )
    addon_offers = []
    for key, btn_marketing in btns_marketing.items():
        addon_offers.append(
            {
                "name": get_from_json(btn_marketing, ["termLength"]),
                "price": float(get_from_json(btn_marketing, ["price"])[1:]),
            }
        )
    detail["addon_offers"] = addon_offers

    detail["pay_later_offers"] = None  # TODO
    detail["max_quantity"] = None  # TODO
    detail["variant"] = {"option_id": variant_option_id}

    subcategories: list[dict[str, Any]] = get_from_json(
        page_props_data, ["crossSell", 0, "tiles"]
    )
    categories: list[dict[str, Any]] = []
    for subcategory in subcategories:
        categories.append(
            {
                "name": get_from_json(subcategory, ["subcategory_title"]),
                "url": f'https://www.bedbathandbeyond.com/{get_from_json(subcategory, ["subcategory_url"])}',
            }
        )
    detail["categories"] = categories

    detail["main_image"] = get_from_json(data_layer_data, ["product_image_url", 0])
    detail["images"] = [
        f'https://ak1.ostkcdn.com/images/products/{get_from_json(img_info, ["cdnPath"])}'
        for img_info in get_from_json(product_data, ["oViewerImages"])
    ]
    detail["labelled_images"] = None

    attributes = get_from_json(
        product_data, ["specificationAttributes", "attributeGroups", 0, "attributes"]
    )
    detail["overview"] = [
        {"name": attr["label"], "value": attr["values"]} for attr in attributes
    ]

    desc_str = get_from_json(product_data, ["description"])
    features = []
    dimensions = []
    status = "none"
    desc_elem = BeautifulSoup(desc_str, "html.parser")
    for child in desc_elem.contents:
        if isinstance(child, str):
            continue
        if status == "none":
            if child.text.strip().lower() == "features:":
                status = "features"
            elif child.text.strip().lower() == "dimensions:":
                status = "dimensions"
        elif status == "features":
            child_elem = BeautifulSoup(str(child), "html.parser")
            elems = child_elem.select("li")
            features = [elem.text.strip() for elem in elems]
            status = "none"
        elif status == "dimensions":
            child_elem = BeautifulSoup(str(child), "html.parser")
            elems = child_elem.select("li")
            dimensions = [elem.text.strip() for elem in elems]
            status = "none"
    detail["features"] = features
    detail["dimensions"] = dimensions

    detail["details_table"] = detail["overview"]
    detail["technical_details"] = None  # TODO
    detail["bestseller_ranks"] = None  # TODO
    detail["seller_name"] = None  # TODO
    detail["seller_url"] = None  # TODO

    options: list[dict[str, Any]] = get_from_json(product_data, ["options"])
    variants: list[dict[str, Any]] = []
    for option in options:
        variants.append(
            {
                "option_id": get_from_json(option, ["optionId"]),
                "description": get_from_json(option, ["decription"]),
                "price": get_from_json(option, ["price"]),
                "listing_price": get_from_json(option, ["comparePrice"]),
                "in_stock": get_from_json(option, ["isInStock"]),
                "url": None,
            }
        )
    detail["variants"] = variants

    detail["reviews_summary"] = None  # TODO

    reviews: list[dict[str, Any]] = get_from_json(
        page_props_data, ["initialPowerReviews", "results", 0, "reviews"]
    )
    aspects: list[dict[str, Any]] = []
    for review in reviews:
        aspects.append(
            {
                "name": get_from_json(review, ["details", "nickname"]),
                "headline": get_from_json(review, ["details", "headline"]),
                "comments": get_from_json(review, ["details", "comments"]),
                "rating": get_from_json(review, ["metrics", "rating"]),
                "helpful_votes": get_from_json(review, ["metrics", "helpful_votes"]),
                "not_helpful_votes": get_from_json(
                    review, ["metrics", "not_helpful_votes"]
                ),
                "helpful_score": get_from_json(review, ["metrics", "helpful_score"]),
                "verified_purchase": get_from_json(
                    review, ["badges", "is_verified_buyer"]
                ),
            }
        )
    detail["review_aspects"] = aspects
    detail["total_reviews"] = get_from_json(
        page_props_data, ["initialPowerReviews", "paging", "total_results"]
    )
    detail["country_of_origin"] = get_from_json(product_data, ["countryOfOrigin"])
    detail["top_reviews"] = None  # TODO
    detail["policy_badges"] = None  # TODO
    detail["product_videos"] = None  # TODO

    contents = get_from_json(product_data, ["productContents"])
    guides = []
    for content in contents:
        guides.append(
            {
                "text": get_from_json(content, ["contentName"]),
                "url": f'https://www.bedbathandbeyond.com{get_from_json(content, ["contentUrl"])}',
            }
        )
    detail["product_guides"] = guides

    detail["warranty_and_support"] = None  # TODO
    detail["from_the_manufacturer"] = None  # TODO
    detail["small_business"] = None  # TODO

    dict_details["detail"] = detail
    dict_details["remaining_credits"] = None

    return dict_details


def main() -> None:
    url = "https://www.bedbathandbeyond.com/Lighting-Ceiling-Fans/13.3-Modern-Matte-Black-3-Light-Crystal-Flush-Mount-Chandelier/36053058/product.html?refccid=6HTD2IHKWJY3Y4SIE5EGK5LLFY&searchidx=0"
    url = "https://www.bedbathandbeyond.com/Home-Garden/Motion-Sensor-13-Gallon-50-Liter-Stainless-Steel-Odorless-Slim-Trash-Can-by-Furniture-of-America/37966526/product.html?refccid=JCHJ6R35HXZ3VHCC6JVZL4PNVA&searchidx=0"
    url = "https://www.bedbathandbeyond.com/Home-Garden/Modern-Sectional-Couch-Comfortable-Upholstered-Sofa-Set-with-Lumbar-Pillow-and-Throw-Pillow-for-Living-Room/41966740/product.html?refccid=RZUUDKKB5PRJ4I2HGWBAMZKWLQ&searchidx=0"
    url = "https://www.bedbathandbeyond.com/Bedding-Bath/Are-You-Kidding-Bare-Coma-Inducer-Oversized-Comforter-Antarctica-Gray/32084702/product.html?refccid=NH4HBGMYILPIHQSANNNRO25RLU&searchidx=0"
    url = "https://www.bedbathandbeyond.com/Home-Garden/Alexander-Home-Megan-Traditional-Area-Rug/32828549/product.html?refccid=SXMGM56V6QZ2472KRRK3BJNXAU&searchidx=0"
    url = "https://www.bedbathandbeyond.com/Lighting-Ceiling-Fans/13.3-Modern-Matte-Black-3-Light-Crystal-Flush-Mount-Chandelier/36053058/product.html?refccid=JPSO3GA7ELHLILSDRK64ZXT73Q&searchidx=1&option=69615223"

    # encode url
    encoded_url = urllib.parse.quote(url, safe=":/")

    api_url = f"https://unwrangledrf.applikuapp.com/api/unblock?url={encoded_url}&render_js=false&premium_proxy=false&country_code=us&api_key=9b4d3f68caa2f7d103813f746b75e44ebb11749e"

    response = requests.get(api_url)
    html_content = response.text
    list_result = parse_bedbathbeyond(html_content=html_content)

    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(
            list_result,
            output_file,
            ensure_ascii=False,
            default=str,
            indent=2,
        )

    logger.info(f"saved to `{output_path}`")


if __name__ == "__main__":
    main()
