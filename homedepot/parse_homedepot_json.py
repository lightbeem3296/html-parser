import json
from typing import Any
from loguru import logger
from pathlib import Path

CUR_DIR = Path(__file__).parent


input_path = CUR_DIR / "homedepot_raw_ca_search.json"
output_path = CUR_DIR.parent / "result" / "homedepot-result.json"


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


def parse_homedepot_json(input_json: list[dict[str, Any]]) -> dict[str, Any]:
    """Parses raw tesco review json and returns parsed result json."""

    output_json: dict[str, Any] = {}

    output_json["success"] = True
    output_json["store_no"] = None
    output_json["zipcode"] = None
    output_json["search"] = get_from_json(input_json, ["searchReport", "currentKeyword"])
    output_json["page"] = None
    output_json["total_results"] = get_from_json(input_json, ["searchReport", "totalProducts"])
    output_json["no_of_pages"] = None
    output_json["result_count"] = None

    results: list[dict[str, Any]] = []

    for product in input_json["products"]:
        results.append(
            {
                "id": get_from_json(product, ["code"]),
                "name": get_from_json(product, ["name"]),
                "model_no": get_from_json(product, ["modelNumber"]),
                "url": f'https://www.homedepot.com{get_from_json(product, ["url"])}',
                "brand": get_from_json(product, ["brand"]),
                "thumbnails": [
                    get_from_json(product, ["imageUrl"]),
                ],
                "price": get_from_json(product, ["pricing", "displayPrice", "value"]),
                "price_reduced": None,
                "currency": get_from_json(product, ["pricing", "displayPrice", "currencyIso"]),
                "rating": get_from_json(product, ["productRating", "averageRating"]),
                "total_reviews": get_from_json(product, ["productRating", "totalReviews"]),
                "favorite_count": None,
                "inventory_quantity": None,
            }
        )

    output_json["result_count"] = len(results)
    output_json["results"] = results

    output_json["meta_data"] = get_from_json(input_json, ["metadata"])
    output_json["remaining_credits"] = None

    return output_json


def main():
    with input_path.open("r") as input_file:
        json_data = json.load(input_file)

        output_json = parse_homedepot_json(json_data)

        with output_path.open("w", encoding="utf-8") as output_file:
            json.dump(output_json, output_file, indent=2, default=str)

        logger.info(f"saved to `{output_path}`")


if __name__ == "__main__":
    main()
