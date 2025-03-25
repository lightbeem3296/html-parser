import base64
import json
import re
import urllib.parse
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup
from loguru import logger

TEST_LOCAL = True

CUR_DIR = Path(__file__).parent

html_path = CUR_DIR / "samsclub_detail_2025-03-20_13-31-07.html"
html_path = CUR_DIR / "samsclub_detail_2025-03-20_13-31-58.html"
html_path = CUR_DIR / "samsclub_detail_2025-03-20_13-27-54.html"
html_path = CUR_DIR / "samsclub_detail_2025-03-20_13-31-09.html"
html_path = CUR_DIR / "samsclub_detail_2025-03-20_13-30-59.html"
html_path = CUR_DIR / "samsclub_detail_2025-03-24_17-16-48.html"
html_path = CUR_DIR / "samsclub_detail_2025-03-24_17-17-17.html"
html_path = CUR_DIR / "samsclub_detail_2025-03-24_17-17-47.html"
html_path = CUR_DIR / "samsclub_detail_2025-03-24_19-00-02.html"
html_path = CUR_DIR / "samsclub_detail_2025-03-24_19-02-58.html"
html_path = CUR_DIR / "samsclub_detail_2025-03-24_18-56-17.html"

output_path = CUR_DIR.parent / "result" / "samsclub-result.json"


def get_from_json(json_obj: dict[str, Any] | None, path: list[str] = []) -> Any:
    obj = json_obj
    for key in path:
        if obj is None:
            break
        if isinstance(key, int):
            if key >= len(obj):
                break
            obj = obj[key]
        elif isinstance(key, str):
            obj = obj.get(key)
    return obj


def parse_html_as_str(html_text: str | None) -> str:
    if not html_text:
        return ""

    soup = BeautifulSoup(html_text, "html.parser")
    return soup.get_text()


def parse_html_as_data(html_text: str | None) -> list:
    ret = []

    if not html_text:
        return ret

    soup = BeautifulSoup(html_text, "html.parser")

    # Handle unordered lists
    ul_elems = soup.select("ul")
    for ul_elem in ul_elems:
        list_data = []
        li_elems = ul_elem.select("li")
        for li_elem in li_elems:
            list_data.append(li_elem.get_text().strip())
        if list_data:
            ret.append(list_data)

    # Handle standalone list items (no parent ul)
    if not ul_elems:
        list_data = []
        li_items = soup.select("li")
        for li_item in li_items:
            list_data.append(li_item.get_text().strip())
        if list_data:
            ret.append(list_data)

    # Handle tables (including those with sections/headers)
    table_elems = soup.select("table")
    for table_elem in table_elems:
        # Check if this is a complex table with sections
        thead_elems = table_elem.select("thead")

        if thead_elems:
            # This is a complex table with sections
            table_data = {}
            current_section = None
            section_items = {}  # Track items for each section

            # Process all rows
            for row in table_elem.select("tr"):
                # Check if this is a header row
                th_elems = row.select("th")
                if th_elems and len(th_elems) > 0:
                    # This is a section header
                    section_text = th_elems[0].get_text().strip()
                    if section_text:
                        current_section = section_text
                        if current_section not in section_items:
                            section_items[current_section] = []
                else:
                    # This is a data row
                    td_elems = row.select("td")
                    if len(td_elems) >= 2:
                        key = td_elems[0].get_text().strip()
                        value = td_elems[1].get_text().strip()

                        # Handle rows with keys and values
                        if key and value:
                            table_data[key] = value
                        # Handle rows with empty first column but content in second column
                        elif not key and value and current_section:
                            # Add to the current section's list
                            if current_section not in table_data:
                                table_data[current_section] = []
                            if isinstance(table_data[current_section], list):
                                table_data[current_section].append(value)
                            else:
                                # If it was previously not a list, convert it
                                old_value = table_data[current_section]
                                table_data[current_section] = [old_value, value]

            if table_data:
                ret.append(table_data)
        else:
            # Standard table processing
            table_data = {}
            tr_elems = table_elem.select("tr")
            for tr_elem in tr_elems:
                td_elems = tr_elem.select("td")
                if len(td_elems) >= 2:
                    key = td_elems[0].get_text().strip()
                    value = td_elems[1].get_text().strip()
                    if key and value:
                        table_data[key] = value
                    # Handle rows with empty first column but content in second column
                    elif not key and value:
                        if "Items" not in table_data:
                            table_data["Items"] = []
                        table_data["Items"].append(value)

            if table_data:
                ret.append(table_data)

    # Handle paragraphs with strong tags (property:value format)
    # Example: <p><strong>Net Volume: </strong>15.99 Liters</p>
    p_data = {}
    p_elems = soup.select("p")
    for p_elem in p_elems:
        strong_elem = p_elem.select_one("strong")
        if strong_elem:
            # Get the property name from the strong tag
            prop_name = strong_elem.get_text().strip()
            # Remove any trailing colons
            prop_name = prop_name.rstrip(":")

            # Get the full paragraph text
            p_text = p_elem.get_text().strip()
            # Extract the value by removing the property name
            prop_value = p_text.replace(strong_elem.get_text(), "", 1).strip()

            if prop_name and prop_value:
                p_data[prop_name] = prop_value

    if p_data:
        ret.append(p_data)

    return ret


def get_products_from_api(product_id: str) -> dict[str, Any]:
    url = "https://www.samsclub.com/api/node/vivaldi/browse/v2/products"

    payload = {
        "productIds": [product_id],
        "type": "LARGE",
        "clubId": "",
    }
    headers = {
        "host": "www.samsclub.com",
        "connection": "keep-alive",
        "sec-ch-ua-platform": '"macOS"',
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "accept": "application/json, text/plain, */*",
        "sec-ch-ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
        "content-type": "application/json",
        "dnt": "1",
        "sec-ch-ua-mobile": "?0",
        "origin": "https://www.samsclub.com",
        "sec-fetch-site": "same-origin",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
        "referer": f"https://www.samsclub.com/p/tramontina-aluminum-fry-pans-set-of-3-assorted-colors/{product_id}?xid=hpg_carousel_rich-relevance.product_0_3",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
        "cookie": f"SSLB=1; vtc=aD41JWyFA4SLLSagy1fqVk; SSRT1=rQjcZwADAA; s_ecid=MCMID%7C04132543087547887273693291396054216962; _gcl_au=1.1.1678157949.1742473390; _pxvid=161c7d9a-0586-11f0-9090-f8b63fea5150; QuantumMetricUserID=8f11bc5d66d17c3f5dfd98178071ee4f; SSID1=CQBCYh0cAAAAAACrCNxnWEdBFKsI3GcBAAAAAABXPb1pqwjcZwBjBk5YAQMMHSoAqwjcZwEA-lUBA7HjKQCrCNxnAQA; SSOD1=ADW3AAAAEgAYtGwAAQAAAK4I3GeuCNxnAQAAAA; samsathrvi=RVI~prod24380340; salsify_session_id=d43057a6-34a5-4b23-86bb-9f59dbe18af4; BVBRANDID=418ea085-f6ba-4825-92c4-a35d58d33ee8; __pxvid=166645fe-0586-11f0-8c6f-0242ac120002; acstkn=87:14#624975973#7=931678458_1742473391063; astract=ca-c796af40-e875-46a9-84e9-a6a0e67416a7; _mibhv=anon-1742473392979-6598855352_4591; rmStore=dmid:8096; _fbp=fb.1.1742473393332.164989035486725929; _tt_enable_cookie=1; _ttp=01JPSR3X7313V402K3QPH6WJ31_.tt.1; _pin_unauth=dWlkPU56azNaV05rWmpndFl6RTFNeTAwTXpBNExUZzRZekF0T0RKallUUTFNVGszWW1JMA; cto_bundle=NogYOl9tMjltaFhaV3dyOGJYaGkxQmdHdk5EaHFSVUhzOUh0OWZhdUFBdXZQSlN0RlR6dDhUWXJVRUFZdlN5N0pnUDZ1bmZNZURvVE5UdTJtQjlTeXdheDJ6ak81YXBiR01KVVQ0UFZwUzVUJTJGOEU4ZyUyQjlZNENHdUJTNGRHd3hjJTJGd2pmcjFzTVl5dkxXQUNHMDhTJTJGQ3dKUklpOFBYcG9Pc2c3JTJCdURqRGFxenc5S21rJTNE; _uetvid=17cfff60058611f0aeb7f5594c149de4; __gads=ID=3d38cf714f3aa417:T=1742473394:RT=1742473394:S=ALNI_Mb1pbZR33UjUXVGMqHCi8q4IjCBFg; __gpi=UID=0000106a8a4ce673:T=1742473394:RT=1742473394:S=ALNI_Ma-ZtGZ2vTdHrhgirm2luAu6NtFMw; __eoi=ID=7992908a68822ab3:T=1742473394:RT=1742473394:S=AA-AfjY9d9SC2tuBOVpG3RqEJ8ut; sxp-rl-SAT_CME-rn=69; sxp-rl-SAT_DISABLE_SYN_PREQUALIFY-rn=29; sxp-rl-SAT_GEO_LOC-rn=46; sxp-rl-SAT_NEW_ORDERS_UI-rn=38; sxp-rl-SAT_ORDER_REPLACEMENT-rn=72; sxp-rl-SAT_REORDER_V4-rn=62; sxp-rl-SCR_CANCEL_ORDER_V3-rn=83; sxp-rl-SCR_CANRV4-rn=47; sxp-rl-SCR_NEXT3-rn=46; sxp-rl-SCR_OHLIMIT-rn=58; sxp-rl-SCR_SHAPEJS-rn=99; sxp-rl-SCR_VERIFICATION_V4-rn=4; sxp-rl-SAT_ADD_ITEM-rn=12; sxp-rl-SCR_SCRE-rn=6; sxp-rl-SCR_TII-rn=35; SAT_WPWCNP=1; bstc=RJSIW93r1sJp0gOWgaTVQA; xpa=t5Tz_; exp-ck=t5Tz_1; SAT_NEO_EXPO=1; sxp-rl-SAT_CME-c=r|1|100; SAT_CME=1; sxp-rl-SAT_DISABLE_SYN_PREQUALIFY-c=r|1|0; SAT_DISABLE_SYN_PREQUALIFY=0; sxp-rl-SAT_GEO_LOC-c=r|1|50; SAT_GEO_LOC=1; sxp-rl-SAT_NEW_ORDERS_UI-c=r|1|0; SAT_NEW_ORDERS_UI=0; sxp-rl-SAT_ORDER_REPLACEMENT-c=r|1|0; SAT_ORDER_REPLACEMENT=0; sxp-rl-SAT_REORDER_V4-c=r|1|0; SAT_REORDER_V4=0; sxp-rl-SCR_CANCEL_ORDER_V3-c=r|1|0; SCR_CANCEL_ORDER_V3=0; sxp-rl-SCR_CANRV4-c=r|1|100; SCR_CANRV4=1; sxp-rl-SCR_NEXT3-c=r|1|100; SCR_NEXT3=1; sxp-rl-SCR_OHLIMIT-c=r|1|0; SCR_OHLIMIT=0; sxp-rl-SCR_SHAPEJS-c=r|1|0; SCR_SHAPEJS=0; sxp-rl-SCR_VERIFICATION_V4-c=r|1|0; SCR_VERIFICATION_V4=0; sxp-rl-SAT_ADD_ITEM-c=r|1|100; SAT_ADD_ITEM=1; sxp-rl-SCR_SCRE-c=r|1|100; SCR_SCRE=1; sxp-rl-SCR_TII-c=r|1|100; SCR_TII=1; xpm=1%2B1742881871%2BaD41JWyFA4SLLSagy1fqVk~%2B1; sams-pt=eyJ4NXQiOiJzOXN6ZUptWldjMWhRYktIOUVqSmNoOUZkTkEiLCJraWQiOiJCM0RCMzM3ODk5OTk1OUNENjE0MUIyODdGNDQ4Qzk3MjFGNDU3NEQwIiwidHlwIjoiSldUIiwiYWxnIjoiUlMyNTYifQ.eyJleHQiOiI4SkZtWW1KbE1HRTBNREV4T0dFNVkyUm1ZbUptTURGaU0yTXpOakk0TnpFME56Qm1OalUxWVRZMVlXWTJOekprTlRBMlpqa3daamsyTnpBeU9XVTRPV0ZpT1RnME5XWmhPVFpqWVRFNFlqTmpNRFUzWmpkak5UTTVZVEZrTkRrd1kyWmpZVE14Wm1NNFlUSmlOREJsWldWa1l6UmxZVGM1WVRNNE4yWTVNalkyTW1NM01tWXlNV0V5TmpReFlXWm1PVEkyTURNelpqazFZams1WldKaU5UZ3oiLCJ2ZXIiOiIxLjAiLCJjaGkiOiJkZXNrdG9wIiwiZmJ0IjpmYWxzZSwiYWhiIjp7InYiOnRydWUsInAiOltdfSwib3ZyZCI6ZmFsc2UsInNoYSI6eyJ2Ijp0cnVlLCJwIjpbXX0sImV4cCI6MTc0Mjg4NTQ3NCwiaWF0IjoxNzQyODgxODc0LCJuYmYiOjE3NDI4ODE4NzQsImlzcyI6Imh0dHBzOi8vdGl0YW4uc2Ftc2NsdWIuY29tL2M4Y2MwNzBlLWRmZWQtNDVjOS1iZGE1LTI5ZDAwMTIxYWNiYi92Mi4wLyIsImp0aSI6IjM2OGM2MTdjLTQ4NTEtNDhmYy1hYmI1LTg0NjEwZmNhNDJkMiJ9.VzfSJ7tjdLYaRUTerjWtoIt1CS0JMJF07Q6eOsOSAirToeWdq-c4OzhdJUE-pDiFlEalva2wN96chflTMw7FWCdQC_mdVyqRyyDatFL8C0KPF8W4nifW_mMTdPOHp3DX5THJfdDXQl43CDFx9yJ5Ql7qKvX-WCz5aN7sL7DU-evCCSozOIge9JkyHjYJ8qWeSOgerSvNSDOu9-_sv2Pknw7vqO8D4HpULKkaiBsDOt1wcP_yXw4c02iHfqxhhi_nOWA9O7z3yixU4_SYVPvbDFNOWor4JZmI9XZZKPiwWjY61qcHGfzA1HI04cWw6693TVpuue_rIA-x9TtOn3lhw96B_ghmfNfG1XckHL37bXRpBg4JUFMw_R7vJ2NrXP9fynrXeD57dsR0qPC7-fLbEnrFWwNtTbJIOppIMpKgZh91xVKVxCoS40wT7CAhliSiuift2z5dG93MK74l0zVEdK6ubEgpHbgD9a1Y6qWYoddpgOapC5Lv8BDshCPPmYcbNhgS6LLSgEw72DhjT-WKgJEpjmpA6Yt9UbA5s6rKFPJbvY_Y1nuUMSflhZ_RIZ4A3MC18-IGFAsoorO6X_d6tZ-KqbozGxEyg8d_ESRk5eHM2seca2kd7iYVRvRqAw8dtD1byInGH7PYMD3hqhJfGbteVzKmg1MbH-YRcGl9b28; ak_bmsc=AC9176AAD2678EF6C1FB47331C2FB53A~000000000000000000000000000000~YAAQ0WncF/yPU6iVAQAAIObayxs+0nEBCbsE2socx2OmAyqUfG4uVrANvmimznpQSLpsBmPfe3EDrmKiXa4kLGQ7lzGbGpiIZZHBGrgM2749gM0o8y/+wS03SM3/IOyY9wG/W36mBJQlFV+qxkl0DKmbC2f5f3/MvqwcXd8qgbG9TPqiEFgiSXcujldXffMAWPndTDAQ0/jH33WLNiMq/ff2NK/f6UnLShjh8nHnm7S+RympqroxBPRNBSFEXyYgz+CuIrzLElr+el+wCeBxeb56UwNjeiU/1CF51o+Pizmg0MW6cCuJDvxQYKzb9MxAQiOl2lKaKgrsYQMrg+RK3xQTornQugA6aHIR8MKjiW/eTiZLd8T+eq8uDuXZGiGu+qe+tKplmPtqp0Mw9i8FUDs=; xptwj=js:12d22df6f93b87a2737d:CvjLSnK9UWS8sTWH529x7tFB5nHpYUNozfUw/gmDgsiDUYv48E+zyJSkC+jyPxhIk++15esXWYOUdUlXv7HWaIgRoz6Dl13zN0FRnmwbJy37Vaynu54=; rcs=eF5jYSlN9rA0T0m2TDQx0jUys0jRNUkzM9M1MDE0AbFMzY3SzCyN04y5cstKMlMEDM2NzXQNdQ0BiSINwQ; AMCVS_B98A1CFE53309C340A490D45%40AdobeOrg=1; AMCV_B98A1CFE53309C340A490D45%40AdobeOrg=1585540135%7CMCIDTS%7C20173%7CMCMID%7C04132543087547887273693291396054216962%7CMCAAMLH-1743486677%7C7%7CMCAAMB-1743486677%7CRKhpRz8krg2tLO6pguXWp5olkAcUniQYPHaMWWgdJ3xzPWQmdj0y%7CMCOPTOUT-1742889077s%7CNONE%7CMCAID%7CNONE%7CvVersion%7C4.4.0; s_cc=true; pxcts=2bce2a7c-093d-11f0-a1d6-d163d12456bd; bm_sv=0D1DBF4EE05CA147B4144066D053FD5F~YAAQ0WncFxyTU6iVAQAABvLayxvPzNs/thnc5wxDjCpUancDaQelL8azXNjb3/zPnyOa7mFjR/nOCvxjUJKAP876uCsWCvBaXUahoQlbvT+Go8e0xG/InEe+JnG5TRiI2fAWpR0DfiroEXYbmNrR5ePPnaJUbP2dL1QkxsxBiYTyqvq6GlZqrUVBvFs1LjCDBHtjGuKIIX8YnjiLIEVelYw4TeBDgn+/WCFMiOrYaqZPI3sreenABTrRGE285lk3byk=~1; _px3=07829f49e7f8450fa334b3eee011cac34d4ebd42eb021dfcd1ddca43fa23993c:xCo5X9gxRRYEIwFdhKPUY6XmFQGOnP7VgFsdQBLNc/uWQcyMtVi7GZzRS9zO/YSQi2S5ItNFQub9oE+Tu5dbqA==:1000:CYoTt/Lef32YfD61c6bMDk5MHcYdR8R6vT1Pu2xTMrTmq59ZH9VZLSwO1J//v0XOO42fXLesBFPNUvEkgKF/Y/hpb7CyDX0saLsWNv8sPP8lkf2/UVX4CbcYtXxZamLnfURrr47P1FiYBrGxT6G/bJ/2a8H2f8QrhJL4KEH3sYyDS4qzOAAubd/9A9KnZrTMajnIN/worIrN7Mw7SPMZFJxr9Qwc8SUzK/RiUew8J5k=; s_sq=samclub3prod%3D%2526c.%2526a.%2526activitymap.%2526page%253Dhomepage%2526link%253DInstant%252520Savings%252520Tramontina%2525203-Piece%252520Nonstick%252520Fry%252520Pan%252520Set%25252C%252520Choose%252520Color%252520%2525281882%252529%252520%2525246%252520off%252520%25252429.84%252520Previous%252520price%25253A%252520%25252429.84%252520From%252520CURRENT%252520P%2526region%253Dmain%2526pageIDType%253D1%2526.activitymap%2526.a%2526.c%2526pid%253Dhomepage%2526pidt%253D1%2526oid%253Dhttps%25253A%25252F%25252Fwww.samsclub.com%25252Fp%25252Ftramontina-aluminum-fry-pans-set-of-3-assorted-colors%25252F{product_id}%25253Fxid%25253Dhpg_c%2526ot%253DA; QuantumMetricSessionID=bbf98e34ac6e6b4b58da2dced3efde4f; _pxde=6f301d72749dcb3da7c2308acef4df5942fbfb1945e1e351145abe37dc391636:eyJ0aW1lc3RhbXAiOjE3NDI4ODE4ODIxNzJ9; seqnum=4; TS017c4a41=0181c636c19af7dcaf60fc876389b9cf95056dccb5f168a8d18a6d893f5a9e91db83c32cc1b621b65f77e067bb31780e20b09873dc; TS01b1959a=0181c636c19af7dcaf60fc876389b9cf95056dccb5f168a8d18a6d893f5a9e91db83c32cc1b621b65f77e067bb31780e20b09873dc; TS017260c8=0181c636c19af7dcaf60fc876389b9cf95056dccb5f168a8d18a6d893f5a9e91db83c32cc1b621b65f77e067bb31780e20b09873dc; TSbdf847b3027=08eb9900a5ab2000ae56f776b27f011377fbb5ff488ed5473a2c52f8aaf0b97cab8e4c3f863a10a8080bbd6d1f11300090fd22d7981d51300ed644cb7b25bb9607b3e45edf3855b330814690a7137722c89a1117d7a2bab460062a382c2d3e4d; akavpau_P1_Sitewide=1742882483~id=46e3490966efc42edbccf8b9e0514be6",
    }

    response = requests.post(url, json=payload, headers=headers)

    return response.json()


def parse_detail(html_content: str) -> dict[str, Any]:
    page_elem = BeautifulSoup(html_content, "html.parser")
    dict_details: dict[str, Any] = {}

    json_data = {}
    product_data = {}
    image_data = []
    messages_data = []
    script_elem = page_elem.select_one("script#tb-djs-wml-redux-state")
    if script_elem is not None:
        json_data_str = script_elem.text
        json_data: dict = json.loads(json_data_str)
        products_data: dict = json_data.get("cache", {}).get("products", {})
        product_data = list(products_data.values())[0]
        product_images: dict = json_data.get("productImages", {})
        image_data = (list(product_images.values())[0]).get("images", [])
        messages_data: list = product_data.get("messages", [])

    # Success
    dict_details["success"] = True

    # Url
    canonical_elem = page_elem.select_one("link[rel=canonical]")
    dict_details["url"] = canonical_elem.attrs.get("href") if canonical_elem else None

    # Result Count
    dict_details["result_count"] = 1

    detail: dict[str, Any] = {}

    # Name
    detail["name"] = get_from_json(product_data, ["descriptors", "name"])

    # Brand
    detail["brand"] = get_from_json(product_data, ["manufacturingInfo", "brand"])

    # Url
    detail["url"] = dict_details.get("url")

    # Highlight
    detail["highlights"] = None
    highlight_text = get_from_json(product_data, ["descriptors", "shortDescription"])
    parsed_data = parse_html_as_data(highlight_text)
    if parsed_data:
        detail["highlights"] = parsed_data[0]

    # Description
    detail["description"] = parse_html_as_str(get_from_json(product_data, ["descriptors", "longDescription"]))

    # Product ID
    detail["product_id"] = get_from_json(product_data, ["productId"])

    # SKU
    detail["sku_id"] = get_from_json(product_data, ["skus", 0, "skuId"])

    # UPC
    detail["upc"] = get_from_json(product_data, ["skus", 0, "onlineOffer", "generatedUPC"])

    # GTIN
    detail["gtin"] = get_from_json(product_data, ["skus", 0, "onlineOffer", "gtin"])

    # Item Number
    detail["item_no"] = get_from_json(product_data, ["skus", 0, "onlineOffer", "itemNumber"])

    # Model Number
    detail["model_no"] = get_from_json(product_data, ["manufacturingInfo", "model"])

    # Image
    detail["main_image"] = get_from_json(image_data, [0, "ImageUrl"])

    # Images
    detail["images"] = [data.get("ImageUrl") for data in image_data]

    # Price
    detail["price"] = get_from_json(product_data, ["skus", 0, "onlineOffer", "price", "finalPrice", "amount"])
    detail["list_price"] = get_from_json(product_data, ["skus", 0, "onlineOffer", "price", "startPrice", "amount"])
    detail["price_per_unit"] = get_from_json(product_data, ["skus", 0, "onlineOffer", "price", "unitPrice", "amount"])

    # Currency
    detail["currency"] = get_from_json(product_data, ["skus", 0, "onlineOffer", "price", "startPrice", "currency"])

    # Demensions & Weight
    weight = get_from_json(product_data, ["skus", 0, "skuLogistics", "weight"])
    if weight:
        detail["weight"] = (
            f"{weight.get('value')} {weight.get('unitOfMeasure')}"
            if weight.get("value") and weight.get("unitOfMeasure")
            else None
        )
        detail["weight_data"] = {"value": weight.get("value"), "unit": weight.get("unitOfMeasure")}
    else:
        detail["weight"] = None
        detail["weight_data"] = None

    # Additional Dimensions
    logistics_data = get_from_json(product_data, ["skus", 0, "skuLogistics"])
    if logistics_data:
        length = logistics_data.get("length", {})
        width = logistics_data.get("width", {})
        height = logistics_data.get("height", {})

        if (
            length.get("value")
            and length.get("unitOfMeasure")
            and width.get("value")
            and width.get("unitOfMeasure")
            and height.get("value")
            and height.get("unitOfMeasure")
        ):
            detail["dimensions"] = (
                f"{length.get('value')}L x {width.get('value')}W x {height.get('value')}H "
                f"{length.get('unitOfMeasure')}"
            )
        else:
            detail["dimensions"] = None

        detail["dimensions_data"] = {
            "box_count": logistics_data.get("numberOfBoxes"),
            "length": {"value": length.get("value"), "unit": length.get("unitOfMeasure")},
            "width": {"value": width.get("value"), "unit": width.get("unitOfMeasure")},
            "height": {"value": height.get("value"), "unit": height.get("unitOfMeasure")},
            "is_hazardous": logistics_data.get("hazardMaterial"),
        }
    else:
        detail["dimensions"] = None
        detail["dimensions_data"] = None

    # Retailer Badge
    savings = get_from_json(product_data, ["skus", 0, "onlineOffer", "price", "savings"])
    if savings:
        detail["buying_offers"] = {
            "amount_saved": get_from_json(savings, ["savingsAmount"]),
            "type": get_from_json(savings, ["memberPromotions", 0, "type"]),
            "max_quantity": get_from_json(savings, ["householdLimit"]),
            "start_date": get_from_json(savings, ["startDate"]),
            "end_date": get_from_json(savings, ["endDate"]),
        }
    else:
        detail["buying_offers"] = None

    # Specifications
    detail["specifications"] = None
    detail["additional_details"] = []
    specifications_text = get_from_json(product_data, ["manufacturingInfo", "specification"])
    parsed_data = parse_html_as_data(specifications_text)

    if parsed_data:
        specs_list = []
        for item in parsed_data:
            # Handle dict-type specifications (from table)
            if isinstance(item, dict):
                for key, value in item.items():
                    # Handle cases where values are lists/arrays
                    if isinstance(value, list):
                        # Add to additional_details as a name-value pair with list value
                        detail["additional_details"].append({"name": key, "value": value})
                    # If it's a section with list values (like Package Contents)
                    elif key in item and isinstance(item[key], list):
                        # Add to additional_details as a name-value pair with list value
                        detail["additional_details"].append({"name": key, "value": item[key]})
                    else:
                        # Regular key-value pair
                        specs_list.append({"name": key, "value": value})
            # Handle list-type specifications (from ul/li)
            elif isinstance(item, list):
                for entry in item:
                    # Try to split entries that might have a colon separator
                    if ":" in entry:
                        name, value = entry.split(":", 1)
                        specs_list.append({"name": name.strip(), "value": value.strip()})
                    else:
                        specs_list.append({"name": "Feature", "value": entry.strip()})

        if specs_list:
            detail["specifications"] = specs_list

        # If no additional_details found, remove the empty list
        if not detail["additional_details"]:
            del detail["additional_details"]

    # Manufacturing Info
    detail["shipping_info"] = []
    detail["warranty"] = parse_html_as_str(get_from_json(product_data, ["manufacturingInfo", "warranty"]))
    detail["country_of_origin"] = get_from_json(product_data, ["manufacturingInfo", "componentCountry"])
    detail["assembled_in"] = get_from_json(product_data, ["manufacturingInfo", "assembledCountry"])
    detail["shipping_info"].append(get_from_json(product_data, ["shippingOption", "info"]))

    # Shipping
    for message in messages_data:
        if message.get("key") == "sidesheet.shipping.upsell.message":
            detail["shipping_info"].append(parse_html_as_str(message.get("message")))
            break

    # Pickup
    detail["curbside_pickup"] = None
    for message in messages_data:
        if message.get("key") == "channelbanner.pickup.message":
            detail["curbside_pickup"] = parse_html_as_str(message.get("message", ""))
            break

    # Returns
    return_info = get_from_json(product_data, ["skus", 0, "returnInfo"])
    if return_info:
        detail["returns"] = {
            "location": return_info.get("returnLocation"),
            "days": return_info.get("returnDays"),
            "policy_text": return_info.get("returnDescription"),
            "policy_link": return_info.get("returnLinkUrl"),
        }
    else:
        detail["returns"] = None

    # Reviews
    detail["rating"] = get_from_json(product_data, ["reviewsAndRatings", "avgRating"])

    # Total Ratings
    detail["total_ratings"] = get_from_json(product_data, ["reviewsAndRatings", "numReviews"])

    # Total Reviews
    detail["total_reviews"] = get_from_json(product_data, ["reviewsAndRatings", "numReviews"])

    # Variants
    variant_options = get_from_json(product_data, ["variantSummary", "variantCriteria"]) or []
    variant_info = get_from_json(product_data, ["variantSummary", "variantInfoMap"]) or []

    variants = []
    for option in variant_options:
        option_type = option.get("name")
        for value in option.get("values", []):
            variant_value = value.get("value")
            variant_image = value.get("imageUrl")

            # Find matching variant info
            for info in variant_info:
                for variant_value_info in info.get("values", []):
                    if (
                        variant_value_info.get("name") == option_type
                        and variant_value_info.get("value") == variant_value
                    ):
                        variants.append(
                            {
                                "type": option_type,
                                "name": variant_value,
                                "sku_id": info.get("variantSkuId"),
                                "family_sku_id": info.get("variantItemGroupId"),
                                "image_url": variant_image,
                            }
                        )

    detail["variants"] = variants

    # Breadcrumbs
    detail["breadcrumbs"] = None
    breadcrumbs = get_from_json(product_data, ["category", "breadcrumbs"])
    if breadcrumbs:
        detail["breadcrumbs"] = [
            {
                "name": get_from_json(a, ["displayName"]),
                "url": get_from_json(a, ["seoUrl"]),
                "nav_id": get_from_json(a, ["navId"]),
            }
            for a in breadcrumbs
        ]

    dict_details["detail"] = detail
    dict_details["remaining_credits"] = None

    return dict_details


def parse_detail_api(html_content: str) -> dict[str, Any]:
    page_elem = BeautifulSoup(html_content, "html.parser")
    dict_details: dict[str, Any] = {}

    html_json_data = {}
    html_product_data = {}
    script_elem = page_elem.select_one("script#tb-djs-wml-redux-state")
    if script_elem is not None:
        json_data_str = script_elem.text
        html_json_data: dict = json.loads(json_data_str)

        html_products_data: dict = html_json_data.get("cache", {}).get("products", {})
        if html_products_data:
            html_product_data = list(html_products_data.values())[0]

    product_id = get_from_json(html_product_data, ["productId"])
    api_resp_data = get_products_from_api(product_id=product_id)
    product_data = {}
    image_data = []
    messages_data = []
    if api_resp_data.get("status") == "SUCCESS":
        product_data = get_from_json(api_resp_data, ["payload", "products", 0])
        product_images: dict = html_json_data.get("productImages", {})
        image_data = (list(product_images.values())[0]).get("images", [])
        messages_data: list = product_data.get("messages", [])

    # Success
    dict_details["success"] = True

    # Url
    canonical_elem = page_elem.select_one("link[rel=canonical]")
    dict_details["url"] = canonical_elem.attrs.get("href") if canonical_elem else None

    # Result Count
    dict_details["result_count"] = 1

    detail: dict[str, Any] = {}

    # Name
    detail["name"] = get_from_json(product_data, ["descriptors", "name"])

    # Brand
    detail["brand"] = get_from_json(product_data, ["manufacturingInfo", "brand"])

    # Url
    detail["url"] = dict_details.get("url")

    # Highlight
    detail["highlights"] = None
    highlight_text = get_from_json(product_data, ["descriptors", "shortDescription"])
    parsed_data = parse_html_as_data(highlight_text)
    if parsed_data:
        detail["highlights"] = parsed_data[0]

    # Description
    detail["description"] = parse_html_as_str(get_from_json(product_data, ["descriptors", "longDescription"]))

    # Product ID
    detail["product_id"] = get_from_json(product_data, ["productId"])

    # SKU
    detail["sku_id"] = get_from_json(product_data, ["skus", 0, "skuId"])

    # UPC
    detail["upc"] = get_from_json(product_data, ["skus", 0, "onlineOffer", "generatedUPC"])

    # GTIN
    detail["gtin"] = get_from_json(product_data, ["skus", 0, "onlineOffer", "gtin"])

    # Item Number
    detail["item_no"] = get_from_json(product_data, ["skus", 0, "onlineOffer", "itemNumber"])

    # Model Number
    detail["model_no"] = get_from_json(product_data, ["manufacturingInfo", "model"])

    # Image
    detail["main_image"] = get_from_json(image_data, [0, "ImageUrl"])

    # Images
    detail["images"] = [data.get("ImageUrl") for data in image_data]

    # Price
    detail["price"] = get_from_json(product_data, ["skus", 0, "onlineOffer", "price", "finalPrice", "amount"])
    detail["list_price"] = get_from_json(product_data, ["skus", 0, "onlineOffer", "price", "startPrice", "amount"])
    detail["price_per_unit"] = get_from_json(product_data, ["skus", 0, "onlineOffer", "price", "unitPrice", "amount"])

    # Currency
    detail["currency"] = get_from_json(product_data, ["skus", 0, "onlineOffer", "price", "startPrice", "currency"])

    # Demensions & Weight
    weight = get_from_json(product_data, ["skus", 0, "skuLogistics", "weight"])
    if weight:
        detail["weight"] = (
            f"{weight.get('value')} {weight.get('unitOfMeasure')}"
            if weight.get("value") and weight.get("unitOfMeasure")
            else None
        )
        detail["weight_data"] = {"value": weight.get("value"), "unit": weight.get("unitOfMeasure")}
    else:
        detail["weight"] = None
        detail["weight_data"] = None

    # Additional Dimensions
    logistics_data = get_from_json(product_data, ["skus", 0, "skuLogistics"])
    if logistics_data:
        length = logistics_data.get("length", {})
        width = logistics_data.get("width", {})
        height = logistics_data.get("height", {})

        if (
            length.get("value")
            and length.get("unitOfMeasure")
            and width.get("value")
            and width.get("unitOfMeasure")
            and height.get("value")
            and height.get("unitOfMeasure")
        ):
            detail["dimensions"] = (
                f"{length.get('value')}L x {width.get('value')}W x {height.get('value')}H "
                f"{length.get('unitOfMeasure')}"
            )
        else:
            detail["dimensions"] = None

        detail["dimensions_data"] = {
            "box_count": logistics_data.get("numberOfBoxes"),
            "length": {"value": length.get("value"), "unit": length.get("unitOfMeasure")},
            "width": {"value": width.get("value"), "unit": width.get("unitOfMeasure")},
            "height": {"value": height.get("value"), "unit": height.get("unitOfMeasure")},
            "is_hazardous": logistics_data.get("hazardMaterial"),
        }
    else:
        detail["dimensions"] = None
        detail["dimensions_data"] = None

    # Retailer Badge
    savings = get_from_json(product_data, ["skus", 0, "onlineOffer", "price", "savings"])
    if savings:
        detail["buying_offers"] = {
            "amount_saved": get_from_json(savings, ["savingsAmount"]),
            "type": get_from_json(savings, ["memberPromotions", 0, "type"]),
            "max_quantity": get_from_json(savings, ["householdLimit"]),
            "start_date": get_from_json(savings, ["startDate"]),
            "end_date": get_from_json(savings, ["endDate"]),
        }
    else:
        detail["buying_offers"] = None

    # Specifications
    detail["specifications"] = None
    detail["additional_details"] = []
    specifications_text = get_from_json(product_data, ["manufacturingInfo", "specification"])
    parsed_data = parse_html_as_data(specifications_text)

    if parsed_data:
        specs_list = []
        for item in parsed_data:
            # Handle dict-type specifications (from table)
            if isinstance(item, dict):
                for key, value in item.items():
                    # Handle cases where values are lists/arrays
                    if isinstance(value, list):
                        # Add to additional_details as a name-value pair with list value
                        detail["additional_details"].append({"name": key, "value": value})
                    # If it's a section with list values (like Package Contents)
                    elif key in item and isinstance(item[key], list):
                        # Add to additional_details as a name-value pair with list value
                        detail["additional_details"].append({"name": key, "value": item[key]})
                    else:
                        # Regular key-value pair
                        specs_list.append({"name": key, "value": value})
            # Handle list-type specifications (from ul/li)
            elif isinstance(item, list):
                for entry in item:
                    # Try to split entries that might have a colon separator
                    if ":" in entry:
                        name, value = entry.split(":", 1)
                        specs_list.append({"name": name.strip(), "value": value.strip()})
                    else:
                        specs_list.append({"name": "Feature", "value": entry.strip()})

        if specs_list:
            detail["specifications"] = specs_list

        # If no additional_details found, remove the empty list
        if not detail["additional_details"]:
            del detail["additional_details"]

    # Manufacturing Info
    detail["shipping_info"] = []
    detail["warranty"] = parse_html_as_str(get_from_json(product_data, ["manufacturingInfo", "warranty"]))
    detail["country_of_origin"] = get_from_json(product_data, ["manufacturingInfo", "componentCountry"])
    detail["assembled_in"] = get_from_json(product_data, ["manufacturingInfo", "assembledCountry"])
    detail["shipping_info"].append(get_from_json(product_data, ["shippingOption", "info"]))

    # Shipping
    for message in messages_data:
        if message.get("key") == "sidesheet.shipping.upsell.message":
            detail["shipping_info"].append(parse_html_as_str(message.get("message")))
            break

    # Pickup
    detail["curbside_pickup"] = None
    for message in messages_data:
        if message.get("key") == "channelbanner.pickup.message":
            detail["curbside_pickup"] = parse_html_as_str(message.get("message", ""))
            break

    # Returns
    return_info = get_from_json(product_data, ["skus", 0, "returnInfo"])
    if return_info:
        detail["returns"] = {
            "location": return_info.get("returnLocation"),
            "days": return_info.get("returnDays"),
            "policy_text": return_info.get("returnDescription"),
            "policy_link": return_info.get("returnLinkUrl"),
        }
    else:
        detail["returns"] = None

    # Reviews
    detail["rating"] = get_from_json(product_data, ["reviewsAndRatings", "avgRating"])

    # Total Ratings
    detail["total_ratings"] = get_from_json(product_data, ["reviewsAndRatings", "numReviews"])

    # Total Reviews
    detail["total_reviews"] = get_from_json(product_data, ["reviewsAndRatings", "numReviews"])

    # Variants
    variant_options = get_from_json(product_data, ["variantSummary", "variantCriteria"]) or []
    variant_info = get_from_json(product_data, ["variantSummary", "variantInfoMap"]) or []

    variants = []
    for option in variant_options:
        option_type = option.get("name")
        for value in option.get("values", []):
            variant_value = value.get("value")
            variant_image = value.get("imageUrl")

            # Find matching variant info
            for info in variant_info:
                for variant_value_info in info.get("values", []):
                    if (
                        variant_value_info.get("name") == option_type
                        and variant_value_info.get("value") == variant_value
                    ):
                        variants.append(
                            {
                                "type": option_type,
                                "name": variant_value,
                                "sku_id": info.get("variantSkuId"),
                                "family_sku_id": info.get("variantItemGroupId"),
                                "image_url": variant_image,
                            }
                        )

    detail["variants"] = variants

    # Breadcrumbs
    detail["breadcrumbs"] = None
    breadcrumbs = get_from_json(product_data, ["category", "breadcrumbs"])
    if breadcrumbs:
        detail["breadcrumbs"] = [
            {
                "name": get_from_json(a, ["displayName"]),
                "url": get_from_json(a, ["seoUrl"]),
                "nav_id": get_from_json(a, ["navId"]),
            }
            for a in breadcrumbs
        ]

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
    list_result = parse_detail(html_content=html_content)

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

        # list_result = parse_detail(html_content=html_content)
        list_result = parse_detail_api(html_content=html_content)

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
