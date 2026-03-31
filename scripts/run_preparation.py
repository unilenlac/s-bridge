import httpx
import json

def main():
    # ==========================================
    # 1. CHOOSE YOUR MODE
    # ==========================================
    # "whole" — single CollatexResponse, optional ref
    # "split" — one file per top-level section written to disk
    mode = "whole"

    # ==========================================
    # 2. CHOOSE YOUR RESOURCES
    # ==========================================
    resources_to_fetch = [
        "athous-iviron-450",
        "athous-iviron-476",
        "brescia-A-III-3-72",
        "ebe-1027"
    ]

    # ==========================================
    # 3. MODE-SPECIFIC SETTINGS
    # ==========================================
    # For "whole" mode: optionally restrict to a sub-reference
    ref = "109"  # e.g. "109" or None for the full text

    # The base URL to your local FastAPI app server
    base_url = "http://127.0.0.1:8000"

    # ==========================================
    print(f"Mode: {mode}")
    print(f"Resources: {resources_to_fetch}")

    try:
        with httpx.Client(timeout=300.0) as client:

            if mode == "whole":
                url = f"{base_url}/dts/prepare-collatex/whole"
                payload = {"resources": resources_to_fetch, "ref": ref}

                print(f"\nCalling: {url}")
                print("Please wait, NLP processing may take a few seconds per witness...\n")

                response = client.post(url, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    output_file = "collatex_output.json"
                    with open(output_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    print(f"Success! Written to '{output_file}'")
                    print(f"Returned {len(data.get('witnesses', []))} witnesses.")
                else:
                    _print_error(response)

            elif mode == "split":
                url = f"{base_url}/dts/prepare-collatex/split"
                payload = {
                    "resources": resources_to_fetch,
                }

                print(f"\nCalling: {url}")
                print("Output directory: collections/[auto-fetched]/")
                print("Please wait, this may take a while (one API call per section per resource)...\n")

                response = client.post(url, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    print(f"Success! {data['total_sections']} section files written:")
                    for path in data["written_files"]:
                        print(f"  {path}")
                else:
                    _print_error(response)

            else:
                print(f"Unknown mode: '{mode}'. Use 'whole' or 'split'.")

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
