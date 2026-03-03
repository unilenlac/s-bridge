import xml.etree.ElementTree as ET

def main() -> None:
    # 1. We wrap the loose fragment in a <root> tag so it is valid XML
    s = '<root><lb n="13"/>δεκα μαθ<del hand="corr1" rend="strike">ηταὶ αὐτοῦ</del>τῶν τοῦ <abbr type="ns">κυ</abbr>· καὶ ἡ ἀδελφὴ αὐτοῦ μαριάμνη· καὶ οἱ ἀκολουθοῦντες αὐτῶ μα"</root>'
    try:
        root = ET.fromstring(s)
        
        # 2. Let's look at the structure ElementTree built!
        print(f"Root tag: {root.tag}")
        print(f"Root .text: {repr(root.text)}")
        
        print("\n--- Children of Root ---")
        for child in root:
            print(f"Tag: <{child.tag}>")
            print(f"  .text = {repr(child.text)}")
            print(f"  .tail = {repr(child.tail)}")
            print(f"  .attrib = {child.attrib}")
            
    except ET.ParseError as e:
        print(f"CRASH: {e}")

if __name__ == "__main__":
    main()
