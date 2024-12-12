from urllib.parse import urlparse, urlunparse
import json
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from loguru import logger

CUR_DIR = Path(__file__).parent

html_path = CUR_DIR / "walmart_search.html"
html_path = CUR_DIR / "walmart_mustard.html"
html_path = CUR_DIR / "walmart_mustard_page_2.html"

output_path = CUR_DIR / "walmart-result.json"


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

    json_data_str = page_elem.select_one("script[id=__NEXT_DATA__]").text
    json_data = json.loads(json_data_str)

    dict_details["success"] = True
    dict_details["search"] = get_from_json(json_data, ["props", "pageProps", "initialSearchQueryVariables", "query"])
    dict_details["page"] = get_from_json(json_data, ["props", "pageProps", "initialSearchQueryVariables", "page"])
    dict_details["total_results"] = get_from_json(
        json_data,
        ["props", "pageProps", "initialData", "searchResult", "aggregatedCount"],
    )
    dict_details["no_of_pages"] = None
    dict_details["result_count"] = 0

    identity_next_tenants_str = get_from_json(
        json_data,
        [
            "props",
            "pageProps",
            "bootstrapData",
            "cv",
            "identity",
            "_all_",
            "identityNextTenants",
        ],
    )
    identity_next_tenants = json.loads(identity_next_tenants_str)
    currency_code = get_from_json(identity_next_tenants, ["currency"])

    results: list[dict[str, Any]] = []
    json_items = get_from_json(
        json_data,
        ["props", "pageProps", "initialData", "searchResult", "itemStacks", 0, "items"],
    )
    for json_item in json_items:
        if get_from_json(json_item, ["__typename"]) != "Product":
            continue

        thumbnail_url = get_from_json(json_item, ["imageInfo", "thumbnailUrl"])
        image_url = urlunparse(urlparse(thumbnail_url)._replace(query=""))

        variants = {}
        for variant_item in get_from_json(json_item, ["variantCriteria"]):
            variant_name = get_from_json(variant_item, ["name"])
            variants[variant_name] = []
            for aa in get_from_json(variant_item, ["variantList"]):
                variants[variant_name].append(
                    {
                        "name": get_from_json(aa, ["name"]),
                        "images": get_from_json(aa, ["images"]),
                        "swatch_image": get_from_json(aa, ["swatchImageUrl"]),
                        "in_stock": get_from_json(aa, ["name"]),
                        "price": None,
                        "id": get_from_json(aa, ["selectedProduct", "usItemId"]),
                        "model_no": get_from_json(aa, ["products", 0]),
                        "url": f'https://www.walmart.com{get_from_json(aa, ["selectedProduct", "canonicalUrl"])}',
                    }
                )

        results.append(
            {
                "id": get_from_json(json_item, ["usItemId"]),
                "name": get_from_json(json_item, ["name"]),
                "url": f'https://www.walmart.com{get_from_json(json_item, ["canonicalUrl"])}',
                "price_reduced": None,
                "price": get_from_json(json_item, ["price"]),
                "currency_code": currency_code,
                "offer_msg": get_from_json(
                    json_item, ["priceInfo", "priceRangeString"]
                ),
                "rating": get_from_json(json_item, ["rating", "averageRating"]),
                "total_reviews": get_from_json(
                    json_item, ["rating", "numberOfReviews"]
                ),
                "in_stock": not get_from_json(json_item, ["isOutOfStock"]),
                "model_no": get_from_json(json_item, ["id"]),
                "description": get_from_json(json_item, ["description"]),
                "image_url": image_url,
                "thumbnail": thumbnail_url,
                "seller_name": get_from_json(json_item, ["sellerName"]),
                "is_sponsored": get_from_json(json_item, ["isSponsoredFlag"]),
                "variants": variants,
                "est_delivery_date": get_from_json(
                    json_item, ["fulfillmentSummary", 0, "deliveryDate"]
                ),
            }
        )

    dict_details["result_count"] = len(results)
    dict_details["results"] = results
    dict_details["meta_data"] = {},
    dict_details["remaining_credits"] = None,

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
