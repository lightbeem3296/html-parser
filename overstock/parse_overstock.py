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

html_path = CUR_DIR / "overstock_detail_2025-02-10_10-45-45.html"
html_path = CUR_DIR / "overstock_detail_2025-02-10_10-45-49.html"
html_path = CUR_DIR / "overstock_detail_2025-02-10_10-45-52.html"
html_path = CUR_DIR / "overstock_detail_2025-02-10_10-45-54.html"
html_path = CUR_DIR / "overstock_detail_2025-02-10_10-45-57.html"
html_path = CUR_DIR / "overstock_detail_2025-02-10_10-46-01.html"
html_path = CUR_DIR / "overstock_detail_2025-02-10_10-46-02.html"
html_path = CUR_DIR / "overstock_detail_2025-02-10_10-46-06.html"
html_path = CUR_DIR / "overstock_detail_2025-02-10_10-46-08.html"

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


def parse_overstock(html_content: str) -> dict[str, Any]:
    page_elem = BeautifulSoup(html_content, "html.parser")
    dict_details: dict[str, Any] = {}

    missing_attrs: dict[str, Any] = {}
    init_data: dict[str, Any] = {}
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
            continue
        if script_elem.attrs.get("id") == "web-pixels-manager-setup":
            pattern = re.compile(
                r"initData:\s*(\{.*?purchasingCompany\"\:null\})\,\}",
                re.DOTALL,
            )
            matches = pattern.findall(script_elem.string)
            json_text = matches[0]
            init_data = json.loads(json_text)
            continue

    dict_details["success"] = True
    dict_details["url"] = get_from_json(missing_attrs, ["url"])
    dict_details["result_count"] = 1

    detail: dict[str, Any] = {}

    detail["name"] = get_from_json(missing_attrs, ["name"])
    detail["brand"] = get_from_json(missing_attrs, ["brand", "name"])
    detail["url"] = get_from_json(missing_attrs, ["url"])
    
    # Description
    description:str = get_from_json(missing_attrs, ["description"])
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

    # Currency
    detail["currency"] = get_from_json(product_variants, [0, "price", "currencyCode"])  # TODO

    detail["currency_symbol"] = None  # TODO
    detail["buying_offers"] = None  # TODO
    detail["other_sellers"] = None  # TODO
    detail["rating"] = None  # TODO
    detail["total_ratings"] = None  # TODO
    detail["past_month_sales"] = None  # TODO
    detail["is_prime"] = None  # TODO
    detail["shipping_info"] = None  # TODO
    detail["delivery_zipcode"] = None  # TODO
    detail["addon_offers"] = None  # TODO
    detail["pay_later_offers"] = None  # TODO
    detail["max_quantity"] = None  # TODO

    # Variant
    detail["variant"] = {
        "id": get_from_json(product_variants, [0, "id"]),
    }

    detail["categories"] = None  # TODO
    detail["main_image"] = None  # TODO
    detail["images"] = None  # TODO
    detail["labelled_images"] = None  # TODO
    detail["overview"] = None  # TODO

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

    detail["details_table"] = None  # TODO
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
            "variant_title": get_from_json(product_variant, ["variant_title"]),
        }
        for product_variant in product_variants
    ]
    detail["reviews_summary"] = None  # TODO
    detail["review_aspects"] = None  # TODO
    detail["total_reviews"] = None  # TODO
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
