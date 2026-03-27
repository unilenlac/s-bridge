import httpx
import json

def main():
    # ==========================================
    # 1. CHOOSE YOUR RESOURCES HERE
    # ==========================================
    # Add or remove witness IDs from this list. 
    # Do not use parameters, just modify this array directly.
    resources_to_fetch = [
        "athous-iviron-450",
        "athous-iviron-476",
        "brescia-A-III-3-72",
        "ebe-1027"
    ]

    
    # Optional: If you want to specify a sub-reference, you can set it here, otherwise keep it None
    ref = "109"
    # ==========================================

    payload = {
        "resources": resources_to_fetch,
        "ref": ref
    }
    
    # The URL to your local FastAPI app server
    url = "http://127.0.0.1:8000/dts/prepare-collatex"
    
    print(f"Calling local API: {url}")
    print(f"Fetching and parsing witnesses: {resources_to_fetch}...")
    print("Please wait, NLP processing may take a few seconds per witness...\n")
    
    try:
        # We set a large timeout (120 seconds) because fetching and parsing 
        # multiple XML documents through the NLP pipeline takes time.
        with httpx.Client(timeout=120.0) as client:
            response = client.post(url, json=payload)
            
            # Check if the server returned a success response
            if response.status_code == 200:
                data = response.json()
                
                # Write the response to an output file
                output_file = "collatex_output.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    
                print(f"Success! Data successfully written to '{output_file}'")
                print(f"Returned {len(data.get('witnesses', []))} witnesses.")
                
            else:
                print(f"API returned an error (Status {response.status_code}):")
                try:
                    # Let's try to parse the error as JSON to make it readable
                    print(json.dumps(response.json(), indent=2))
                except:
                    print(response.text)
                
    except httpx.RequestError as e:
        print(f"Network error while connecting to {e.request.url}: {e}")
        print("Make sure your FastAPI server is currently running in another terminal!")

if __name__ == "__main__":
    main()
