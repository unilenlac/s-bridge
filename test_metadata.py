from cltk import NLP
from bs4 import BeautifulSoup
import json
from main import get_metadata_for_token, collatex_token_from_doc, process_tei_to_collatex


def test_unclear_metadata():
    xml = '''<div><p>και <unclear reason="illegible">οι</unclear> συν</p></div>'''
    soup = BeautifulSoup(xml, features="xml")
    nlp = NLP("grc", backend="stanza", suppress_banner=True)
    clean_text, metadata_map = process_tei_to_collatex(soup)
    doc = nlp.analyze(clean_text)
    tokens = collatex_token_from_doc(doc, metadata_map)
    unclear_token = next((t for t in tokens if t.get("unclear")), None)
    print("TEST: Unclear metadata")
    print(f"  Clean text: '{clean_text}'")
    if unclear_token:
        print(f"  Token: {unclear_token['t']}, unclear={unclear_token.get('unclear')}, reason={unclear_token.get('unclear_reason')}")
        print("  ✓ PASSED\n")
    else:
        print(f"  ✗ FAILED\n")
    return tokens


def test_add_metadata():
    xml = '''<div><p>εμειναν <add hand="manus1">κατεχοντες</add> τον</p></div>'''
    soup = BeautifulSoup(xml, features="xml")
    nlp = NLP("grc", backend="stanza", suppress_banner=True)
    clean_text, metadata_map = process_tei_to_collatex(soup)
    doc = nlp.analyze(clean_text)
    tokens = collatex_token_from_doc(doc, metadata_map)
    add_token = next((t for t in tokens if t.get("add")), None)
    print("TEST: Add metadata")
    print(f"  Clean text: '{clean_text}'")
    if add_token:
        print(f"  Token: {add_token['t']}, add={add_token.get('add')}, hand={add_token.get('add_hand')}")
        print("  ✓ PASSED\n")
    else:
        print(f"  ✗ FAILED\n")
    return tokens


def test_hyphenated_break():
    xml = '''<div><p><add hand="manus1">κατε<lb break="no"/>χοντες</add> και</p></div>'''
    soup = BeautifulSoup(xml, features="xml")
    nlp = NLP("grc", backend="stanza", suppress_banner=True)
    clean_text, metadata_map = process_tei_to_collatex(soup)
    doc = nlp.analyze(clean_text)
    tokens = collatex_token_from_doc(doc, metadata_map)
    add_tokens = [t for t in tokens if t.get('add')]
    print("TEST: Hyphenated break")
    print(f"  Clean text: '{clean_text}'")
    print(f"  Tokens with add: {[t['t'] for t in add_tokens]}")
    for t in add_tokens:
        if '-' in t['t']:
            print(f"  ✗ FAILED: Hyphen in {t['t']}\n")
            return tokens
    print("  ✓ PASSED\n")
    return tokens


if __name__ == "__main__":
    print("="*60)
    print("METADATA TESTS")
    print("="*60 + "\n")
    test_unclear_metadata()
    test_add_metadata()
    test_hyphenated_break()
    print("="*60)
    print("TESTS COMPLETE")
    print("="*60)
