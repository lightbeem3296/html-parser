import json
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from loguru import logger

CUR_DIR = Path(__file__).parent

html_path = CUR_DIR / "wayfair_category.html"

output_path = CUR_DIR / "wayfair-category-result.json"


def get_from_json(json_obj: dict[str, Any] | None, path: list[str] = []) -> Any:
    obj = json_obj
    for key in path:
        if obj is None:
            break
        obj = obj.get(key)
    return obj


def parse_wayfair_html(html_content: str) -> dict[str, Any]:
    """Parses wayfair product html content and returns parsed product detail as json."""

    list_results: list[dict[str, Any]] = []

    page_elem = BeautifulSoup(html_content, "html.parser")

    data_json = None
    try:
        script = page_elem.select("script")[-2]
        script_str = script.text
        script_str = script_str.split('window["WEBPACK_ENTRY_DATA"]')[-1].strip(
            "=; \t\r\n"
        )
        script_str = script_str[:-1].strip("; \t\r\n")
        data_json = json.loads(script_str)
    except:  # noqa: E722
        logger.warning("failed json loading. progress with html content only")

    product_data_list = get_from_json(data_json, ["application", "props", "browse", "browse_grid_objects"])
    for product_data in product_data_list:
        image_url = None
        pricing_data = get_from_json(product_data, ["raw_pricing_data", "pricing"])
        list_results.append(
            {
                "sku": get_from_json(product_data, ["sku"]),
                "url": get_from_json(product_data, ["url"]),
                "name": get_from_json(product_data, ["product_name"]),
                "manufacturer": get_from_json(product_data, ["manufacturer"]),
                "image_url": image_url,
                "free_ship_text": get_from_json(product_data, ["free_ship_text"]),
                "average_overall_rating": get_from_json(product_data, ["average_overall_rating"]),
                "review_count": get_from_json(product_data, ["review_count"]),
                "features": get_from_json(product_data, ["features_array"]),
                "romance_copy": get_from_json(product_data, ["romance_copy"]),
                "customer_price": get_from_json(pricing_data, ["customerPrice", "quantityPrice", "value"]),
                "everyday_price": get_from_json(pricing_data, ["everydayPrice", "quantityPrice", "value"]),
                "list_price": get_from_json(pricing_data, ["listPrice", "quantityPrice", "value"]),
                "currency": get_from_json(pricing_data, ["customerPrice", "quantityPrice", "currency"]),
            }
        )
    return list_results


def main():
    with html_path.open("r", encoding="utf-8") as html_file:
        html_content = html_file.read()

        product_detail = parse_wayfair_html(html_content)

        with output_path.open("w", encoding="utf-8") as file:
            json.dump(product_detail, file, indent=2, ensure_ascii=False)

        logger.info(f"saved to `{output_path}`")


if __name__ == "__main__":
    main()
