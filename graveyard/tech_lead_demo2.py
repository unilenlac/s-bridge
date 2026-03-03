import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

# This XML string has a tag (<add>) that is opened but NEVER closed.
# It is simply missing the closing </add> tag entirely.
dirty_xml = """<p>The manuscript says <add>Hello, but the scribe crossed out <del>world</del>. And then the paragraph ends.</p>"""


print("=== ATTEMPT 1: ElementTree (Native, Strict) ===")
try:
    tree = ET.fromstring(dirty_xml)
    print("SUCCESS: ElementTree parsed it.")
except Exception as e:
    print(f"CRASH: ElementTree failed with error: {e}")

print("\n")

print("=== ATTEMPT 2: BeautifulSoup (Third-Party, Forgiving) ===")
try:
    soup = BeautifulSoup(dirty_xml, 'xml')
    print("SUCCESS: BeautifulSoup parsed it without crashing.")
    
    # Let's see how BeautifulSoup artificially "healed" the missing tags
    print("\nHow BeautifulSoup hallucinated the missing tags:")
    print("-" * 40)
    print(soup.prettify())
    print("-" * 40)
except Exception as e:
    print(f"CRASH: BeautifulSoup failed with error: {e}")
