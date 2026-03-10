import requests
import json
import argparse
import sys

def convert_text(input_file, output_file, mode="full"):
    """
    Sends Greek text from an input file to the NLP server and saves the JSON output.
    """
    url = "http://localhost:8000/convert"
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            text = f.read()
            
        print(f"Sending text from {input_file} to NLP server (mode: {mode})...")
        
        # We pass parameters via query params
        params = {
            "text": text,
            "mode": mode
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()  # check for HTTP errors
        
        data = response.json()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        print(f"Successfully saved {len(data)} tokens to {output_file}")
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send Greek text to the NLP Server")
    parser.add_argument("input_file", help="Path to the file containing Greek text/XML")
    parser.add_argument("output_file", help="Path to the output JSON file to save results")
    parser.add_argument("--mode", choices=["full", "simple"], default="full", 
                        help="Parsing mode: 'full' (default, expects XML) or 'simple' (raw text)")
    
    args = parser.parse_args()
    
    convert_text(args.input_file, args.output_file, args.mode)
