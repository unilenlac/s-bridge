import httpx
import os

def main():
    # ==========================================
    # 1. CHOOSE YOUR RESOURCE ID HERE
    # ==========================================
    # Change this string to fetch a different XML witness
    resource_id = "athous-iviron-450"
    # ==========================================
    
    url = "http://ftsr-dev.unil.ch:8000/api/dts/v1/document/"
    params = {"resource": resource_id}
    
    print(f"Fetching XML for resource '{resource_id}'...")
    print(f"From: {url}?resource={resource_id}")
    
    try:
        with httpx.Client() as client:
            # We don't need a huge timeout here because we're just 
            # grabbing the raw XML directly without running NLP on it.
            response = client.get(url, params=params)
            
            # Raise an error if the server returned 404, 500, etc.
            response.raise_for_status()
            
            # The DTS document API returns the raw XML string
            xml_content = response.text
            
            # Save it to a clearly named XML file in the project log/root
            output_file = f"{resource_id}.xml"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(xml_content)
                
            print(f"✅ Success! XML successfully written to '{output_file}'")
            print(f"File size: {len(xml_content):,} characters")
            
    except httpx.HTTPStatusError as e:
        print(f"❌ API Error (Status {e.response.status_code}): {e.response.text}")
    except Exception as e:
        print(f"❌ A network error occurred: {e}")

if __name__ == "__main__":
    main()
