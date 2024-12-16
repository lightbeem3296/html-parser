import json
from typing import Any
from loguru import logger
from pathlib import Path

CUR_DIR = Path(__file__).parent


input_path = CUR_DIR / "tesco_reviews_raw.json"

output_path = CUR_DIR / "tesco-result.json"


def parse_tesco_json(input_json: list[dict[str, Any]]) -> dict[str, Any]:
    """Parses raw tesco review json and returns parsed result json."""

    json_data = input_json[0]
    output_json: dict[str, Any] = {}

    output_json["offset"] = json_data["data"]["reviews"]["info"]["offset"]
    output_json["total"] = json_data["data"]["reviews"]["info"]["total"]
    output_json["page"] = json_data["data"]["reviews"]["info"]["page"]
    output_json["count"] = json_data["data"]["reviews"]["info"]["count"]
    output_json["product_tpnb"] = json_data["data"]["reviews"]["product"]["tpnb"]
    output_json["product_tpnc"] = json_data["data"]["reviews"]["product"]["tpnc"]
    output_json["overall_rating"] = json_data["data"]["reviews"]["stats"][
        "overallRating"
    ]
    output_json["overall_rating_range"] = json_data["data"]["reviews"]["stats"][
        "overallRatingRange"
    ]
    output_json["no_of_reviews"] = json_data["data"]["reviews"]["stats"]["noOfReviews"]

    reviews: list[dict[str, Any]] = []

    for entry in json_data["data"]["reviews"]["entries"]:
        reviews.append(
            {
                "review_id": entry["reviewId"],
                "submission_time": entry["submissionDateTime"],
                "rating_value": entry["rating"]["value"],
                "rating_range": entry["rating"]["range"],
                "author_name": entry["author"]["nickname"],
                "is_authored_by_me": entry["author"]["authoredByMe"],
                "status": entry["status"],
                "summary": entry["summary"],
                "text": entry["text"],
                "is_syndicated": entry["syndicated"],
                "syndication_soure_name": entry["syndicationSource"]["name"],
            }
        )

    output_json["review_list"] = reviews

    return output_json


def main():
    with input_path.open("r") as input_file:
        json_data = json.load(input_file)

        output_json = parse_tesco_json(json_data)

        with output_path.open("w", encoding="utf-8") as output_file:
            json.dump(output_json, output_file, indent=2, default=str)

        logger.info(f"saved to `{output_path}`")


if __name__ == "__main__":
    main()
