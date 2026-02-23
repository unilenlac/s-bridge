import pytest
from bs4 import BeautifulSoup
from tokenize_xml import extract_normalized_text_and_metadata

def get_metadata_for_word(word_start, word_end, metadata_map):
    """Helper mirroring the tokenizer's logic to fetch metadata for a specific character range."""
    token_metadata = {}
    for map_start, map_stop, metadata in metadata_map:
        if word_start < map_stop and word_end > map_start:
            token_metadata.update(metadata)
    return token_metadata

def find_word_range(text, target_word):
    """Simple string finder for test targeting."""
    start = text.find(target_word)
    if start == -1:
        return -1, -1
    return start, start + len(target_word)

def test_basic_text_extraction():
    xml = "<root>Hello world</root>"
    soup = BeautifulSoup(xml, "xml")
    clean_text, meta = extract_normalized_text_and_metadata(soup)
    assert clean_text == "Hello world"
    assert len(meta) == 0

def test_lb_break_no_joining():
    # word "hyphenated" split across lb tag with a physical hyphen and trailing/leading whitespace.
    xml = "<root>This is a hy-<lb break='no'/>\n     phenated word.</root>"
    soup = BeautifulSoup(xml, "xml")
    clean_text, meta = extract_normalized_text_and_metadata(soup)
    assert clean_text == "This is a hyphenated word."

def test_lb_normal_break():
    # normal <lb/> should be replaced by space
    xml = "<root>Line 1<lb/>Line 2</root>"
    soup = BeautifulSoup(xml, "xml")
    clean_text, meta = extract_normalized_text_and_metadata(soup)
    assert clean_text == "Line 1 Line 2"

def test_pb_normal_break():
    # normal <pb/> should be replaced by space
    xml = "<root>Page 1<pb n='2'/>Page 2</root>"
    soup = BeautifulSoup(xml, "xml")
    clean_text, meta = extract_normalized_text_and_metadata(soup)
    assert clean_text == "Page 1 Page 2"

def test_unclear_tag_metadata():
    xml = '<root>Here is an <unclear reason="illegible">obscure</unclear> text.</root>'
    soup = BeautifulSoup(xml, "xml")
    clean_text, meta = extract_normalized_text_and_metadata(soup)
    assert clean_text == "Here is an obscure text."
    
    start, end = find_word_range(clean_text, "obscure")
    word_meta = get_metadata_for_word(start, end, meta)
    assert word_meta.get("unclear") is True
    assert word_meta.get("unclear_reason") == "illegible"

def test_add_tag_metadata():
    xml = '<root>The editor <add hand="scribe1">added</add> this.</root>'
    soup = BeautifulSoup(xml, "xml")
    clean_text, meta = extract_normalized_text_and_metadata(soup)
    
    start, end = find_word_range(clean_text, "added")
    word_meta = get_metadata_for_word(start, end, meta)
    assert word_meta.get("add") is True
    assert word_meta.get("add_hand") == "scribe1"

def test_del_tag_metadata():
    xml = '<root>The writer <del rend="strike">removed</del> this.</root>'
    soup = BeautifulSoup(xml, "xml")
    clean_text, meta = extract_normalized_text_and_metadata(soup)
    
    start, end = find_word_range(clean_text, "removed")
    word_meta = get_metadata_for_word(start, end, meta)
    assert word_meta.get("del") is True
    assert word_meta.get("del_reason") == "strike"
    
def test_del_tag_fallback_reason():
    xml = '<root>The writer <del>removed</del> this without a rend attribute.</root>'
    soup = BeautifulSoup(xml, "xml")
    clean_text, meta = extract_normalized_text_and_metadata(soup)
    
    start, end = find_word_range(clean_text, "removed")
    word_meta = get_metadata_for_word(start, end, meta)
    assert word_meta.get("del") is True
    assert word_meta.get("del_reason") == "other"

def test_abbr_tag_metadata():
    xml = '<root>He spoke to the <abbr type="ns">kyrios</abbr>.</root>'
    soup = BeautifulSoup(xml, "xml")
    clean_text, meta = extract_normalized_text_and_metadata(soup)
    
    start, end = find_word_range(clean_text, "kyrios")
    word_meta = get_metadata_for_word(start, end, meta)
    assert word_meta.get("abbr") is True
    assert word_meta.get("abbr_type") == "ns"

def test_nested_tags():
    # <unclear> and <add> applied to the same word
    xml = '<root><add hand="m1"><unclear reason="faded">nested</unclear></add></root>'
    soup = BeautifulSoup(xml, "xml")
    clean_text, meta = extract_normalized_text_and_metadata(soup)
    
    assert clean_text == "nested"
    start, end = find_word_range(clean_text, "nested")
    word_meta = get_metadata_for_word(start, end, meta)
    
    assert word_meta.get("add") is True
    assert word_meta.get("add_hand") == "m1"
    assert word_meta.get("unclear") is True
    assert word_meta.get("unclear_reason") == "faded"

def test_hyphenated_with_metadata():
    # Test our complex bug fix from earlier where 'hyphenated' has metadata on one half
    xml = '<root><unclear reason="ink">hy-</unclear><lb break="no"/>phenated</root>'
    soup = BeautifulSoup(xml, "xml")
    clean_text, meta = extract_normalized_text_and_metadata(soup)
    
    assert clean_text == "hyphenated"
    start, end = find_word_range(clean_text, "hyphenated")
    word_meta = get_metadata_for_word(start, end, meta)
    
    # The unclear tag should apply to the word
    assert word_meta.get("unclear") is True
    assert word_meta.get("unclear_reason") == "ink"

def test_punctuation():
    # Verify that punctuation maintains spacing rules properly alongside normal words.
    xml = '<root>Hello, world! Welcome.</root>'
    soup = BeautifulSoup(xml, "xml")
    clean_text, meta = extract_normalized_text_and_metadata(soup)
    
    assert clean_text == "Hello, world! Welcome."
