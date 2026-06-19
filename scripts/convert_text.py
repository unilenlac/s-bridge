import requests
import json
import argparse
import sys


def convert_text(
    input_file,
    output_file,
    format="tei",
    strategy="enriched",
    normalization="lemma",
):
    """
    Sends Greek text from an input file to the NLP server and saves the JSON output.
    """
    url = "http://localhost:8000/convert"

    try:
        with open(input_file, "r", encoding="utf-8") as f:
            text = f.read()

        print(
            f"Sending text from {input_file} to NLP server (format: {format}, strategy: {strategy}, normalization: {normalization})..."
        )

        # We pass parameters via query params
        params = {
            "format": format,
            "strategy": strategy,
            "normalization": normalization,
        }

        response = requests.post(url, params=params, json={"text": text})
        response.raise_for_status()  # check for HTTP errors

        data = response.json()

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Successfully saved {len(data)} tokens to {output_file}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send Greek text to the NLP Server")
    parser.add_argument("input_file", help="Path to the file containing Greek text/XML")
    parser.add_argument(
        "output_file", help="Path to the output JSON file to save results"
    )
    parser.add_argument(
        "--format",
        choices=["tei", "json", "text"],
        default="tei",
        help="Data format of the input file (default: tei)",
    )
    parser.add_argument(
        "--strategy",
        choices=["enriched", "raw"],
        default="enriched",
        help="Parsing strategy logic (default: enriched)",
    )
    parser.add_argument(
        "--normalization",
        choices=["lemma+pos", "lemma", "text"],
        default="lemma",
        help="Token normalization string (default: lemma)",
    )

    args = parser.parse_args()

    convert_text(
        args.input_file,
        args.output_file,
        args.format,
        args.strategy,
        args.normalization,
    )
