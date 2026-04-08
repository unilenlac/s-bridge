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
    ref = ""

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
            url = f"{base_url}/dts/process-and-collate"
            payload = {"resources": resources_to_fetch, "ref": ref}
            params = {"output_format": output_format}

            print(f"\nCalling: {url}")
            print("Please wait, NLP processing and collation may take a few seconds...\n")

            response = client.post(url, json=payload, params=params)
            if response.status_code == 200:
                data = response.json()
                job_id = data.get("job_id")
                print(f"Job launched successfully! Job ID: {job_id}")
                print("Polling for completion...")

                import time
                while True:
                    time.sleep(3)
                    job_resp = client.get(f"{base_url}/dts/jobs/{job_id}")
                    if job_resp.status_code != 200:
                        print(f"Error polling job status... status code {job_resp.status_code}")
                        break
                    
                    job_data = job_resp.json()
                    status = job_data.get("status")
                    print(f"Current Status: {status}...")
                    
                    if status in ["COMPLETED", "FAILED", "CANCELLED"]:
                        print(f"\nJob finished with final state: {status}")
                        if status == "FAILED":
                            print(f"Error Message: {job_data.get('error_message')}")
                        elif status == "COMPLETED":
                            trad_resp = client.get(f"{base_url}/dts/traditions")
                            if trad_resp.status_code == 200:
                                all_traditions = trad_resp.json()
                                job_results = [t for t in all_traditions if t.get("job_id") == job_id]
                                
                                if job_results:
                                    print(f"Success! Collation completed for {len(job_results)} sections.")
                                    collection = job_results[0].get("resource_id", "Unknown")
                                    print(f"Results stored in '{collection}':")
                                    
                                    results_dict = {}
                                    for t in job_results:
                                        print(f"  [{t['ref']}]: {t['result_path']}")
                                        results_dict[t['ref']] = t['result_path']
                                    
                                    summary_data = {
                                        "collection": collection,
                                        "job_id": str(job_id),
                                        "total_sections": len(job_results),
                                        "results": results_dict
                                    }
                                    
                                    with open("collate_results_summary.json", "w", encoding="utf-8") as f:
                                        json.dump(summary_data, f, indent=2, ensure_ascii=False)
                                    print(f"\nSummary written to 'collate_results_summary.json'")
                                else:
                                    print("\nJob completed, but no physical results were tracked in the database.")
                        break
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
