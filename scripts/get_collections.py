import httpx
import json

def get_collection(client, url, collection_id=None):
    params = {"nav": "children", "limit": 100}
    if collection_id:
        params["id"] = collection_id
        
    response = client.get(url, params=params)
    response.raise_for_status()
    return response.json()

def main():
    url = "http://ftsr-dev.unil.ch:8000/api/dts/v1/collection"
    print(f"Fetching root collections from {url}...\n")
    
    discovery_tree = []
    
    try:
        with httpx.Client() as client:
            # 1. Fetch Root
            root_data = get_collection(client, url)
            root_members = root_data.get("member", [])
            
            for collection in root_members:
                col_id = collection.get("@id")
                col_title = collection.get("title", "Untitled")
                col_type = collection.get("@type", "Unknown")
                
                print(f"📦 COLLECTION: {col_title} (ID: {col_id})")
                
                col_node = {
                    "id": col_id,
                    "title": col_title,
                    "type": str(col_type).lower(),
                    "children": []
                }
                
                if str(col_type).lower() == "collection":
                    # 2. Fetch the resources inside this collection
                    try:
                        child_data = get_collection(client, url, col_id)
                        child_members = child_data.get("member", [])
                        
                        if not child_members:
                            print("   ↳ (Empty collection)")
                            
                        for child in child_members:
                            child_id = child.get("@id", "N/A")
                            child_title = child.get("title", "Untitled")
                            child_type = child.get("@type", "Resource")
                            
                            # Add an extra visual indicator for resources
                            icon = "📄" if str(child_type).lower() == "resource" else "📁"
                            print(f"   ↳ {icon} {child_type}: {child_title} (ID: {child_id})")
                            
                            col_node["children"].append({
                                "id": child_id,
                                "title": child_title,
                                "type": str(child_type).lower()
                            })
                    except Exception as e:
                        print(f"   ↳ ❌ Failed to fetch children: {e}")
                print("-" * 60)
                discovery_tree.append(col_node)
                
            # Dump the fully assembled discovery tree to a JSON file
            output_file = "collections_output.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(discovery_tree, f, indent=2, ensure_ascii=False)
            print(f"\n✅ Full hierarchical discovery tree saved to '{output_file}'")
                
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()

