import json
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from loguru import logger

CUR_DIR = Path(__file__).parent

html_path = CUR_DIR / "tesco_detail.html"
output_path = CUR_DIR / "tesco-detail-result.json"


def get_from_json(json_obj: dict[str, Any] | None, path: list[str] = []) -> Any:
    obj = json_obj
    for key in path:
        if obj is None:
            break
        obj = obj.get(key)
    return obj


def parse_tesco_html(html_content: str) -> list[dict[str, Any]]:
    """Parses html content and returns a list of product information."""

    page_elem = BeautifulSoup(html_content, "html.parser")
    dict_details: dict[str, Any] = {}

    json_data_str = page_elem.select_one("script[type='application/discover+json']").text
    json_data = json.loads(json_data_str)

    # product id
    product_id = get_from_json(json_data, ["mfe-global-scripts", "props", "route", "params", "productId"])
    dict_details["id"] = product_id

    # name
    product_data = get_from_json(json_data, ["mfe-orchestrator", "props", "apolloCache", f"ProductType:{product_id}"])
    dict_details["name"] = get_from_json(product_data, ["title"])

    # brand
    dict_details["brand"] = get_from_json(product_data, ["brandName"])

    # url
    dict_details["url"] = f"https://www.tesco.com/groceries/en-GB/products/{product_id}"

    # image
    dict_details["image_url"] = get_from_json(product_data, ["defaultImageUrl"])

    # price
    dict_details["price"] = get_from_json(product_data, ["price", "actual"])

    # currency
    dict_details["currency"] = get_from_json(json_data, ["mfe-pdp", "props", "config", "client", "isoCurrencyCode"])

    # gtin
    dict_details["gtin"] = get_from_json(product_data, ["gtin"])

    # tpn
    dict_details["tpnb"] = get_from_json(product_data, ["tpnb"])
    dict_details["tpnc"] = get_from_json(product_data, ["tpnc"])

    # description
    dict_details["description"] = get_from_json(product_data, ["description"])

    # pack size
    dict_details["pack_size"] = []
    pack_sizes = get_from_json(product_data, ["details", "packSize"])
    if pack_sizes is not None:
        for pack_size in pack_sizes:
            dict_details["pack_size"].append({
                "value": get_from_json(pack_size, ["value"]),
                "units": get_from_json(pack_size, ["units"]),
            })

    # storage
    dict_details["storage"] = get_from_json(product_data, ["details", "storage"])

    # nutrition
    dict_details["nutrition"] = []
    nutritions = get_from_json(product_data, ["details", "nutrition"])
    if nutritions is not None:
        for nutrition in nutritions:
            dict_details["nutrition"].append({
                "name": get_from_json(nutrition, ["name"]),
                "value1": get_from_json(nutrition, ["value1"]),
                "value2": get_from_json(nutrition, ["value2"]),
                "value3": get_from_json(nutrition, ["value3"]),
                "value4": get_from_json(nutrition, ["value4"]),
            })

    # reviews & rating
    rating_value = 0.0
    rating_count = 0
    reviews = []
    for key in product_data:
        if key.startswith("reviews"):
            review = product_data[key]
            rating_value = get_from_json(review, ["stats", "overallRating"])
            rating_count = get_from_json(review, ["stats", "noOfReviews"])
            
            entries = get_from_json(review, ["entries"])
            if entries is not None:
                for entry in entries:
                    reviews.append({
                        "rating": get_from_json(entry, ["rating", "value"]),
                        "author": get_from_json(entry, ["author", "nickname"]),
                        "status": get_from_json(entry, ["status"]),
                        "summary": get_from_json(entry, ["summary"]),
                        "text": get_from_json(entry, ["text"]),
                        "is_syndicated": get_from_json(entry, ["syndicated"]),
                        "syndication_source": get_from_json(entry, ["syndicationSource", "name"]),
                    })
            break
    dict_details["rating_value"] = rating_value
    dict_details["rating_count"] = rating_count
    dict_details["reviews"] = reviews

    return dict_details


def main() -> None:
    with html_path.open("r", encoding="utf-8") as html_file:
        html_content = html_file.read()

        list_result = parse_tesco_html(html_content=html_content)

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
