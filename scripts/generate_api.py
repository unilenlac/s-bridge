#!/usr/bin/env python3
"""Script to generate the OpenAPI JSON schema for the s-bridge FastAPI application."""

import argparse
import json
import os
import sys

# Ensure the root directory is in the sys.path so main.py can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app  # noqa: E402


def generate_openapi(output_path: str) -> None:
    """Generates the OpenAPI JSON schema for the FastAPI app and writes it to a file."""
    print("Generating OpenAPI schema...")
    # Retrieve the OpenAPI schema dictionary
    openapi_schema = app.openapi()

    # Write the schema to the specified JSON file
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2, ensure_ascii=False)

    print(f"Successfully generated OpenAPI schema at: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate the OpenAPI specification JSON file for σ-Bridge NLP Server."
    )
    parser.add_argument(
        "-o",
        "--output",
        default="openapi.json",
        help="Path where the OpenAPI JSON file should be saved (default: openapi.json)",
    )
    args = parser.parse_args()

    # Resolve output path relative to the workspace root if not absolute
    output_filepath = os.path.abspath(args.output)
    generate_openapi(output_filepath)
