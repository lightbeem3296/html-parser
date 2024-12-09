import json
from typing import Any
from loguru import logger
from pathlib import Path

CUR_DIR = Path(__file__).parent


input_path = CUR_DIR / "tesco_reviews_raw.json"

output_path = CUR_DIR / "tesco-result.json"


def parse_tesco_json(input_path: Path, output_path: Path) -> None:
    with input_path.open("r", encoding="utf-8") as input_file:
        input_json = json.load(input_file)[0]
        output_json: dict[str, Any] = {}

        output_json["offset"] = input_json["data"]["reviews"]["info"]["offset"]
        output_json["total"] = input_json["data"]["reviews"]["info"]["total"]
        output_json["page"] = input_json["data"]["reviews"]["info"]["page"]
        output_json["count"] = input_json["data"]["reviews"]["info"]["count"]
        output_json["product_tpnb"] = input_json["data"]["reviews"]["product"]["tpnb"]
        output_json["product_tpnc"] = input_json["data"]["reviews"]["product"]["tpnc"]
        output_json["overall_rating"] = input_json["data"]["reviews"]["stats"]["overallRating"]
        output_json["overall_rating_range"] = input_json["data"]["reviews"]["stats"]["overallRatingRange"]
        output_json["no_of_reviews"] = input_json["data"]["reviews"]["stats"]["noOfReviews"]

        reviews: list[dict[str, Any]] = []

        for entry in input_json["data"]["reviews"]["entries"]:
            reviews.append(
                {
                    "review_id": entry["reviewId"],
                    "submission_time": entry["submissionDateTime"],
                    "rating_value": entry["rating"]["value"],
                    "rating_range": entry["rating"]["range"],
                    "author_name": entry["author"]["nickname"],
                    "authored_by_me": entry["author"]["authoredByMe"],
                    "status": entry["status"],
                    "summary": entry["summary"],
                    "text": entry["text"],
                    "syndicated": entry["syndicated"],
                    "syndication_soure_name": entry["syndicationSource"]["name"],
                }
            )

        output_json["review_list"] = reviews

        with output_path.open("w", encoding="utf-8") as output_file:
            json.dump(output_json, output_file, indent=2, default=str)

        logger.info(f"saved to `{output_path}`")


def main():
    parse_tesco_json(input_path, output_path)


if __name__ == "__main__":
    main()
