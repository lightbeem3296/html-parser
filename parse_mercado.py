import re
import json
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from loguru import logger

CUR_DIR = Path(__file__).parent

html_path = CUR_DIR / "mercado_search.html"
output_path = CUR_DIR / "mercado-result.json"


def get_from_json(json_obj: dict[str, Any] | None, path: list[str] = []) -> Any:
    obj = json_obj
    for key in path:
        if obj is None:
            break
        obj = obj.get(key)
    return obj


def parse_mercado_html(html_content: str) -> list[dict[str, Any]]:
    """Parses html content and returns a list of product information."""

    page_elem = BeautifulSoup(html_content, "html.parser")

    card_elems = page_elem.select("li.ui-search-layout__item")
    list_results: list[dict[str, Any]] = []

    for card_elem in card_elems:
        name_str = card_elem.select_one("h2").text
        name = re.sub(r'\s{2,}', ' ', name_str)

        image = card_elem.select_one("img").attrs["src"]
        if image.startswith("data:image"):
            image = card_elem.select_one("img").attrs["data-src"]

        brand = card_elem.select_one("span.poly-component__brand").text

        rating_value = 0.0
        rating_count = 0
        review_elem = card_elem.select_one("div.poly-component__reviews")
        if review_elem is not None:
            review_str = review_elem.select_one("span.andes-visually-hidden").text
            rating_value = float(review_str.split()[1].strip())
            rating_count = int(review_str.splitlines()[0].split("(")[1].strip())

        price_elem = card_elem.select_one("div.poly-price__current")
        currency = price_elem.select_one("span.andes-money-amount__currency-symbol").text
        price_fraction_str = price_elem.select_one("span.andes-money-amount__fraction").text
        price_cents_elem = price_elem.select_one("span.andes-money-amount__cents")
        price_cents_str = "00" if price_cents_elem is None else price_cents_elem.text
        price = float(f"{price_fraction_str}.{price_cents_str}")

        listing_price = None
        price_elem = card_elem.select_one("s.andes-money-amount--previous")
        if price_elem is not None:
            currency = price_elem.select_one("span.andes-money-amount__currency-symbol").text
            price_fraction_str = price_elem.select_one("span.andes-money-amount__fraction").text
            price_cents_elem = price_elem.select_one("span.andes-money-amount__cents")
            price_cents_str = "00" if price_cents_elem is None else price_cents_elem.text
            listing_price = float(f"{price_fraction_str}.{price_cents_str}")

        url = card_elem.select_one("a").attrs["href"]

        list_results.append(
            {
                "name": name,
                "image": image,
                "brand": brand,
                "rating_value": rating_value,
                "rating_count": rating_count,
                "price": price,
                "listing_price": listing_price,
                "currenty": currency,
                "url": url,
            }
        )

    return list_results


def main() -> None:
    with html_path.open("r", encoding="utf-8") as html_file:
        html_content = html_file.read()

        list_result = parse_mercado_html(html_content=html_content)

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
