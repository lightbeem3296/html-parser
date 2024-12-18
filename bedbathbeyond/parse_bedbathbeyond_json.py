import json
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from loguru import logger

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


def parse_walmart_html(html_content: str) -> list[dict[str, Any]]:
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
    detail["description"] = get_from_json(product_data, ["shortDescription"])
    detail["asin"] = None  # TODO
    detail["retailer_badge"] = None  # TODO
    detail["deal_badge"] = None  # TODO
    detail["listing_id"] = get_from_json(product_data, ["id"])
    detail["price"] = get_from_json(product_data, ["memberPrice"])
    detail["price_reduced"] = None  # TODO
    detail["price_per_unit"] = None  # TODO
    detail["currency"] = get_from_json(data_layer_data, ["order_currency"])
    detail["currency_symbol"] = get_from_json(product_data, ["priceSet", 0, "symbol"])
    detail["buying_offers"] = []  # TODO
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
    detail["addon_offers"] = None  # TODO
    detail["pay_later_offers"] = None  # TODO
    detail["max_quantity"] = None  # TODO
    detail["variant"] = {"option_id": get_from_json(product_data, ["defaultOptionId"])}

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

    detail["features"] = None  # TODO
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
            }
        )
    detail["review_aspects"] = aspects

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


def main() -> None:
    with html_path.open("r", encoding="utf-8") as html_file:
        html_content = html_file.read()

        list_result = parse_walmart_html(html_content=html_content)

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
