import httpx
import json

def main():
    # ==========================================
    # 1. CHOOSE YOUR RESOURCES
    # ==========================================
    resources_to_fetch = [
        "athous-iviron-450",
        "athous-iviron-476",
        "brescia-A-III-3-72",
        "ebe-1027"
    ]

    # ==========================================
    # 2. CONFIGURE COLLATION SETTINGS
    # ==========================================
    # Optionally restrict to a sub-reference (e.g. "109" or None for full text)
    ref = "109"

    # Output format options:
    # - "application/json" (default)
    # - "application/tei+xml"
    # - "text/plain"
    # - "application/graphml+xml"
    # - "image/svg+xml"
    output_format = "application/json"

    # The base URL to your local FastAPI app server
    base_url = "http://127.0.0.1:8000"

    # ==========================================
    print(f"Resources: {resources_to_fetch}")
    print(f"Reference: {ref if ref else 'Full text'}")
    print(f"Output format: {output_format}")

    try:
        with httpx.Client(timeout=300.0) as client:
            url = f"{base_url}/dts/collate"
            payload = {"resources": resources_to_fetch, "ref": ref}
            params = {"output_format": output_format}

            print(f"\nCalling: {url}")
            print("Please wait, NLP processing and collation may take a few seconds...\n")

            response = client.post(url, json=payload, params=params)
            if response.status_code == 200:
                # Determine output file extension based on format
                ext_map = {
                    "application/json": ".json",
                    "application/tei+xml": ".xml",
                    "text/plain": ".txt",
                    "application/graphml+xml": ".graphml",
                    "image/svg+xml": ".svg",
                }
                ext = ext_map.get(output_format, ".txt")
                output_file = f"collate_output{ext}"

                # Write output based on format
                if output_format == "application/json":
                    data = response.json()
                    with open(output_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                else:
                    # For non-JSON formats (TEI, SVG, etc.), write as text
                    with open(output_file, "w", encoding="utf-8") as f:
                        f.write(response.text)

                print(f"Success! Written to '{output_file}'")
            else:
                _print_error(response)

    except httpx.RequestError as e:
        print(f"Network error while connecting to {e.request.url}: {e}")
        print("Make sure your FastAPI server is running in another terminal!")


def _print_error(response):
    print(f"API returned an error (Status {response.status_code}):")
    try:
        print(json.dumps(response.json(), indent=2))
    except Exception:
        print(response.text)


if __name__ == "__main__":
    main()
