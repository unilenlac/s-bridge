import httpx
import json


def get_traditions():
    base_url = "http://127.0.0.1:8000"
    url = f"{base_url}/dts/traditions"

    print(f"Fetching completed traditions from {url}...\n")
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)

            if response.status_code == 200:
                traditions = response.json()
                if not traditions:
                    print("No traditions found. The database is empty.")
                    return

                print(f"Found {len(traditions)} completed tradition(s):\n")

                for t in traditions:
                    created = t.get("created_at", "Unknown")
                    if created != "Unknown":
                        # Clean up milliseconds from ISO datetime display if present
                        created = created.split(".")[0].replace("T", " ")

                    print(f"- Tradition ID: {t.get('id')}")
                    print(f"  Resource: {t.get('resource_id')}")
                    print(f"  Reference: {t.get('ref') or 'Full text'}")
                    print(f"  File Path: {t.get('result_path')}")
                    print(f"  Job UUID: {t.get('job_id')}")
                    print(f"  Created: {created}")
                    print("-" * 40)
            else:
                print(
                    f"Failed to fetch traditions. Status Code: {response.status_code}"
                )
                try:
                    print(json.dumps(response.json(), indent=2))
                except Exception:
                    print(response.text)

    except httpx.RequestError as e:
        print(f"Network error while connecting to {e.request.url}: {e}")
        print("Make sure your FastAPI server is running!")


if __name__ == "__main__":
    get_traditions()
