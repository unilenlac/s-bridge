import xml.etree.ElementTree as ET

def main() -> None:
    # 1. We wrap the loose fragment in a <root> tag so it is valid XML
    s = '<root><lb n="13"/>δεκα μαθ<del hand="corr1" rend="strike">ηταὶ αὐτοῦ</del>τῶν τοῦ <abbr type="ns">κυ</abbr>· καὶ ἡ ἀδελφὴ αὐτοῦ μαριάμνη· καὶ οἱ ἀκολουθοῦντες αὐτῶ μα"</root>'
    
    dummy_data = """<div>""" \
            """<pb n="f.193v"/>""" \
            """<lb n="1"/><hi>κ</hi>ατὰ τὸν καιρὸν ἐκεῖνον τραϊανοῦ τοῦ βασιλέως παρειληφότος τῆν τῶν ρω-""" \
            """<lb n="2" break="no"/>μαίων ἀρχὴν· μετὰ τὸ μαρτυρῆσαι ἐν ὀγδόω ἔτει τῆς βασιλείας αὐτοῦ σίμω-""" \
            """<lb n="3" break="no"/>να τὸν τοῦ κλωπᾶ <seg>ἐπίσκοπον</seg> ὄντα ϊεροσολύμων· δεύτερον γενόμενον""" \
            """<lb n="4"/>ἐπίσης τοῦ μετὰ ἰάκωβον τὸν χρηματίσαντα ἀδελφὸν τοῦ κυρίου· τῆς""" \
            """<lb n="5"/>ἐκεῖσε ἐκκλησίας· φίλιππος ὁ ἀπόστολος διἐρχόμενος τὰ τῆς λυδίας καὶ ἀσίας""" \
            """<lb n="6"/>πόλεις καὶ χώρας κατήγγειλεν πάσιν τὸ εὐαγγέλιον τοῦ χριστοῦ· """ \
            """</div>"""
    try:
        root = ET.fromstring(dummy_data)
        
        # 2. Let's look at the structure ElementTree built!
        # print(f"Root tag: {root.tag}")
        # print(f"Root .text: {repr(root.text)}")
        
        for Element in root.iter():
            
            print(Element.tail)
            # root.remove(child)

        print(f"\n{dummy_data}")
        # print("\n--- Children of Root ---")
        # for child in root:
        #     print(f"Tag: <{child.tag}>")
        #     print(f"  .text = {repr(child.text)}")
        #     print(f"  .tail = {repr(child.tail)}")
        #     print(f"  .attrib = {child.attrib}")
            
    except ET.ParseError as e:
        print(f"CRASH: {e}")

    for parent in root.iter():
        for child in list(parent):
            if child.tag in ['lb','pb']:
                child_index = list(parent).index(child)

                # Case A: Prior text is attached to a previous sibling's tail
                if child_index > 0:
                    prev_sibling = parent[child_index - 1]
                    prior_text = prev_sibling.tail or ""

                    if prior_text.rstrip().endswith('-'):
                        clean_prior = prior_text.rstrip()[:-1]
                        rescued_tail = (child.tail or "").lstrip()
                        prev_sibling.tail = clean_prior + rescued_tail
                    else:
                        prev_sibling.tail = prior_text + " " + (child.tail or "")

                # Case B: Prior text is the parent's text directly
                else:
                    prior_text = parent.text or ""
                    if prior_text.rstrip().endswith('-'):
                        clean_prior = prior_text.rstrip()[:-1]
                        rescued_tail = (child.tail or "").lstrip()
                        parent.text = clean_prior + rescued_tail
                    else:
                        parent.text = prior_text + " " + (child.tail or "")
            
            parent.remove(child)

        print(ET.tostring(root, encoding='unicode'))



if __name__ == "__main__":
    main()
