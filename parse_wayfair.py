import re
import json
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from loguru import logger

CUR_DIR = Path(__file__).parent

html_path = CUR_DIR / "wayfair-variation.html"
html_path = CUR_DIR / "wayfair_detail_2024-12-08_12-53-17.html"
html_path = CUR_DIR / "wayfair_detail_2024-12-08_12-53-05.html"
html_path = CUR_DIR / "wayfair_detail_2024-12-08_12-51-54.html"
output_path = CUR_DIR / "wayfair-result.json"


def get_from_json(json_obj: dict[str, Any] | None, path: list[str] = []) -> Any:
    obj = json_obj
    for key in path:
        if obj is None:
            break
        obj = obj.get(key)
    return obj


def parse(html_path: Path, output_path: Path):
    result: dict[str, Any] = {}
    result["success"] = True

    with html_path.open("r", encoding="utf-8") as file:
        page_elem = BeautifulSoup(file.read(), "html.parser")
        content_elem = page_elem.select_one("div[id='sf-ui-browse::application']")

        data_json = None
        try:
            data_json = json.loads(page_elem.select("script")[-4].text.splitlines()[4].strip()[29:-1])
        except:  # noqa: E722
            pass
        product_data = get_from_json(data_json, ["application", "props", "productData"])
        price_data = get_from_json(product_data, ["price"])

        # ================================
        # Product url
        # ================================
        result["product_url"] = page_elem.select_one("link[rel=canonical]").attrs["href"]

        # ================================
        # Result count
        # ================================
        result["result_count"] = 1

        # ================================
        # Name
        # ================================
        detail: dict[str, Any] = {}
        detail["name"] = content_elem.select_one("a.HotDealsProductTitle").text.strip()

        # ================================
        # Main Image
        # ================================
        detail["main_image"] = content_elem.select_one("div.ProductDetailSingleMediaViewer").select_one("img").attrs["src"]

        # ================================
        # Images
        # ================================
        list_elem = content_elem.select_one("ul.HotDealsThumbnailCarousel-container")
        item_elem_list = list_elem.select("li")
        images: list[str] = []
        for item_elem in item_elem_list:
            image_link = item_elem.select_one("img").attrs["src"]
            if image_link.startswith("data:image"):
                continue
            image_link = image_link.replace("timg-h56-w56%5Ecompr-r70", "resize-h1600-w1600%5Ecompr-r85")
            images.append(image_link)
        detail["images"] = images

        # ================================
        # Price
        # ================================
        price = get_from_json(price_data, ["customerPrice", "quantityPrice", "value"])
        if price is None:
            price_elem = content_elem.select_one("div.BasePriceBlock")
            if price_elem is not None:
                price_str = price_elem.text
                match = re.search(r"[-+]?\d{1,3}(?:,\d{3})*(?:\.\d+)?", price_str)
                if match:
                    clean_str = match.group(0).replace(',', '')
                    price = float(clean_str)
                else:
                    raise ValueError(f"Invalid input: {price_str}")
        detail["price"] = price

        # ================================
        # List Price
        # ================================
        list_price = None
        price_elem = content_elem.select_one("div.BasePriceBlock--list")
        if price_elem is not None:
            match = re.search(r"[-+]?\d{1,3}(?:,\d{3})*(?:\.\d+)?", price_elem.text)
            if match:
                clean_str = match.group(0).replace(',', '')
                list_price = float(clean_str)
            else:
                raise ValueError(f"Invalid input: {price_str}")
        if list_price is None:
            list_price = get_from_json(price_data, ["listPrice", "quantityPrice", "value"])
        detail["list_price"] = list_price

        # ================================
        # Currency
        # ================================
        currency = get_from_json(price_data, ["customerPrice", "quantityPrice", "currency"])
        if currency is None:
            price_str = content_elem.select_one("div.BasePriceBlock").text
            currency = price_str[:1]
        detail["currency"] = currency

        # ================================
        # Description
        # ================================
        detail["description"] = None

        # ================================
        # SKU ID
        # ================================
        detail["sku_id"] = content_elem.select_one("form.HotDealsCallToActionForm").select_one("input[name=sku]").attrs["value"]

        # ================================
        # Brand
        # ================================
        brand_str = content_elem.select_one("p.HotDealsProductTitle-manufacturerName").text
        detail["brand"] = brand_str.replace("By", "").strip()

        # ================================
        # Rating
        # ================================
        rating_str_list = content_elem.select_one("button[data-hb-id=ReviewStars]>p").contents
        detail["rating"] = float(rating_str_list[0].split()[1].strip())

        # ================================
        # Total ratings
        # ================================
        detail["total_ratings"] = int(rating_str_list[2].split()[0].strip())

        # ================================
        # Total reviews
        # ================================
        detail["total_reviews"] = None

        # ================================
        # Reviews
        # ================================
        detail["reviews"] = []

        # ================================
        # Retailer Badge
        # ================================
        detail["retailer_badge"] = None

        # ================================
        # Variant
        # ================================
        detail["variant"] = {}

        # ================================
        # Variants
        # ================================
        detail["variants"] = []

        # ================================
        # Product overview
        # ================================
        detail["product_overview"] = get_from_json(product_data, ["overview"])

        # ================================
        # Delivery Zipcode
        # ================================
        detail["delivery_postal_code"] = get_from_json(product_data, ["delivery", "postal_code"])
        detail["delivery_postal_code_city"] = get_from_json(product_data, ["delivery", "postal_code_city"])

        # ================================
        # Shipping Info
        # ================================
        detail["shipping_info"] = None
        
        # ================================
        # Features
        # ================================
        detail["features"] = None

        # ================================
        # at-a-glance
        # ================================
        detail["at-a-glance"] = None

        result["detail"] = detail

        # ================================
        # Remaining credits
        # ================================
        result["remaining_credits"] = None

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(result, file, indent=2, ensure_ascii=False)

    logger.info(f"saved to `{output_path}`")


def main():
    parse(html_path, output_path)


if __name__ == "__main__":
    main()
