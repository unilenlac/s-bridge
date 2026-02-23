import re
import json
import os

file_path = "Le Martyre de Philippe - Acta Philippi/milestone_108.xml"

with open(file_path, "r", encoding="utf-8") as f:
    text = f.read()

# Parse the malformed text using regex to extract id and content
witnesses = []
pattern = r'\{\s*"id"\s*:\s*"(.*?)"\s*,\s*"content"\s*:\s*"(.*?)"\s*\}'
matches = re.finditer(pattern, text, re.DOTALL)

for match in matches:
    wid = match.group(1)
    content = match.group(2)
    witnesses.append({
        "id": wid,
        "content": content
    })

# 1. Output purely JSON file
json_out_path = "Le Martyre de Philippe - Acta Philippi/milestone_108.json"
json_data = {"milestone n='108'": witnesses}
with open(json_out_path, "w", encoding="utf-8") as f:
    json.dump(json_data, f, ensure_ascii=False, indent=4)

# 2. Output purely XML file (TEI-like)
xml_out_path = "Le Martyre de Philippe - Acta Philippi/milestone_108_pure.xml"
xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n<milestone n="108">\n'
for w in witnesses:
    xml_content += f'  <witness id="{w["id"]}">\n'
    # wrap in p if not already
    c = w["content"].strip()
    if not c.startswith("<p>"):
        c = f"<p>{c}</p>"
    
    # Indent content nicely
    c = "\n".join("    " + line.strip() for line in c.split("\n"))
    xml_content += f'{c}\n'
    xml_content += '  </witness>\n'
xml_content += '</milestone>\n'

with open(xml_out_path, "w", encoding="utf-8") as f:
    f.write(xml_content)

print("Created milestone_108.json and milestone_108_pure.xml")
