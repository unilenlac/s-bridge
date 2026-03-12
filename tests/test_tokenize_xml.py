import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import xml.etree.ElementTree as ET
from nlp_server.cls.TEIParser import TEIParser

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

def get_parser():
    return TEIParser()

def test_basic_text_extraction():
    xml = "<root>Hello world</root>"
    parser = get_parser()
    clean_text, meta = parser.parse(xml)
    assert clean_text == "Hello world"
    assert len(meta) == 0

def test_lb_break_no_joining():
    # word "hyphenated" split across lb tag with a physical hyphen and trailing/leading whitespace.
    xml = "<root>This is a hy-<lb break='no'/>\n     phenated word.</root>"
    parser = get_parser()
    clean_text, meta = parser.parse(xml)
    assert clean_text == "This is a hyphenated word."

def test_lb_normal_break():
    # normal <lb/> should be replaced by space
    xml = "<root>Line 1<lb/>Line 2</root>"
    parser = get_parser()
    clean_text, meta = parser.parse(xml)
    assert clean_text == "Line 1 Line 2"

def test_pb_normal_break():
    # normal <pb/> should be replaced by space
    xml = "<root>Page 1<pb n='2'/>Page 2</root>"
    parser = get_parser()
    clean_text, meta = parser.parse(xml)
    assert clean_text == "Page 1 Page 2"

def test_unclear_tag_metadata():
    xml = '<root>An <unclear reason="illegible"/>obscure text.</root>'
    parser = get_parser()
    clean_text, meta = parser.parse(xml)
    assert clean_text == "An obscure text."
    
    start, end = find_word_range(clean_text, "obscure")
    word_meta = get_metadata_for_word(start, end, meta)
    assert word_meta.get("unclear") is True
    assert word_meta.get("unclear_reason") == "illegible"

    # Verify preceding word does not have 'unclear'
    start_before, end_before = find_word_range(clean_text, "An")
    meta_before = get_metadata_for_word(start_before, end_before, meta)
    assert meta_before.get("unclear") is None

    # Verify following word does not have 'unclear'
    start_after, end_after = find_word_range(clean_text, "text")
    meta_after = get_metadata_for_word(start_after, end_after, meta)
    assert meta_after.get("unclear") is None

def test_unclear_tag_wrapped_word():
    xml = '<root>One <unclear reason="faded">faded</unclear> word.</root>'
    parser = get_parser()
    clean_text, meta = parser.parse(xml)
    assert clean_text == "One faded word."
    
    start, end = find_word_range(clean_text, "faded")
    word_meta = get_metadata_for_word(start, end, meta)
    assert word_meta.get("unclear") is True
    assert word_meta.get("unclear_reason") == "faded"

    # Verify preceding word does not have 'unclear'
    start_before, end_before = find_word_range(clean_text, "One")
    meta_before = get_metadata_for_word(start_before, end_before, meta)
    assert meta_before.get("unclear") is None

    # Verify following word does not have 'unclear'
    start_after, end_after = find_word_range(clean_text, "word")
    meta_after = get_metadata_for_word(start_after, end_after, meta)
    assert meta_after.get("unclear") is None

def test_unclear_tag_inside_split_word():
    # Tag is in the middle of a continuous word
    xml = '<root>Here is an ob<unclear reason="illegible"/>scure text.</root>'
    parser = get_parser()
    clean_text, meta = parser.parse(xml)
    assert clean_text == "Here is an obscure text."
    
    start, end = find_word_range(clean_text, "obscure")
    word_meta = get_metadata_for_word(start, end, meta)
    assert word_meta.get("unclear") is True
    assert word_meta.get("unclear_reason") == "illegible"

    # Verify preceding word does not have 'unclear'
    start_before, end_before = find_word_range(clean_text, "an")
    meta_before = get_metadata_for_word(start_before, end_before, meta)
    assert meta_before.get("unclear") is None

    # Verify following word does not have 'unclear'
    start_after, end_after = find_word_range(clean_text, "text")
    meta_after = get_metadata_for_word(start_after, end_after, meta)
    assert meta_after.get("unclear") is None

def test_unclear_tag_with_trailing_space():
    # Tag is placed after the word, followed by a space
    xml = '<root>here is an obscu<unclear reason="damage"/> text.</root>'
    parser = get_parser()
    clean_text, meta = parser.parse(xml)
    assert clean_text == "here is an obscu text."
    
    start, end = find_word_range(clean_text, "obscu")
    word_meta = get_metadata_for_word(start, end, meta)
    assert word_meta.get("unclear") is True
    assert word_meta.get("unclear_reason") == "damage"

    # Verify following word does not have 'unclear'
    start_after, end_after = find_word_range(clean_text, "text")
    meta_after = get_metadata_for_word(start_after, end_after, meta)
    assert meta_after.get("unclear") is None

def test_add_tag_metadata():
    xml = '<root>The editor <add hand="scribe1">added</add> this.</root>'
    parser = get_parser()
    clean_text, meta = parser.parse(xml)
    
    start, end = find_word_range(clean_text, "added")
    word_meta = get_metadata_for_word(start, end, meta)
    assert word_meta.get("add") is True
    assert word_meta.get("add_hand") == "scribe1"

def test_del_tag_metadata():
    xml = '<root>The writer <del rend="strike">removed</del> this.</root>'
    parser = get_parser()
    clean_text, meta = parser.parse(xml)
    
    start, end = find_word_range(clean_text, "removed")
    word_meta = get_metadata_for_word(start, end, meta)
    assert word_meta.get("del") is True
    assert word_meta.get("del_reason") == "strike"
    
def test_del_tag_fallback_reason():
    xml = '<root>The writer <del>removed</del> this without a rend attribute.</root>'
    parser = get_parser()
    clean_text, meta = parser.parse(xml)
    
    start, end = find_word_range(clean_text, "removed")
    word_meta = get_metadata_for_word(start, end, meta)
    assert word_meta.get("del") is True
    assert word_meta.get("del_reason") == "other"

def test_abbr_tag_metadata():
    xml = '<root>He spoke to the <abbr type="ns">kyrios</abbr>.</root>'
    parser = get_parser()
    clean_text, meta = parser.parse(xml)
    
    start, end = find_word_range(clean_text, "kyrios")
    word_meta = get_metadata_for_word(start, end, meta)
    assert word_meta.get("abbr") is True
    assert word_meta.get("abbr_type") == "ns"

def test_nested_tags():
    # <unclear> and <add> applied to the same word
    xml = '<root><add hand="m1"><unclear reason="faded"/>nested</add></root>'
    parser = get_parser()
    clean_text, meta = parser.parse(xml)
    
    assert clean_text == "nested"
    start, end = find_word_range(clean_text, "nested")
    word_meta = get_metadata_for_word(start, end, meta)
    
    assert word_meta.get("add") is True
    assert word_meta.get("add_hand") == "m1"
    assert word_meta.get("unclear") is True
    assert word_meta.get("unclear_reason") == "faded"

def test_hyphenated_with_metadata():
    # Test our complex bug fix from earlier where 'hyphenated' has metadata on one half
    xml = '<root><unclear reason="ink"/>hy-<lb break="no"/>phenated</root>'
    parser = get_parser()
    clean_text, meta = parser.parse(xml)
    
    assert clean_text == "hyphenated"
    start, end = find_word_range(clean_text, "hyphenated")
    word_meta = get_metadata_for_word(start, end, meta)
    
    # The unclear tag should apply to the word
    assert word_meta.get("unclear") is True
    assert word_meta.get("unclear_reason") == "ink"

def test_punctuation():
    # Verify that punctuation maintains spacing rules properly alongside normal words.
    xml = '<root>Hello, world! Welcome.</root>'
    parser = get_parser()
    clean_text, meta = parser.parse(xml)
    
    assert clean_text == "Hello, world! Welcome."

def test_abbr_expansion_logic():
    xml = '<root>Here is the <abbr type="nom_sac">κς</abbr>.</root>'
    parser = get_parser()
    parser.abbr_dict = {"κς": "κύριος"}
    clean_text, meta = parser.parse(xml)
    
    assert clean_text == "Here is the κύριος."
    start, end = find_word_range(clean_text, "κύριος")
    word_meta = get_metadata_for_word(start, end, meta)
    
    assert word_meta.get("abbr") is True
    assert word_meta.get("abbr_original") == "κς"
    assert word_meta.get("abbr_type") == "nom_sac"

def test_aggressive_hyphenation():
    # Test our aggressive merging: a hyphen before a normal <lb/> (no break="no")
    xml = "<root>This is completely a hy-<lb/>\n     phenated word.</root>"
    parser = get_parser()
    clean_text, meta = parser.parse(xml)
    assert clean_text == "This is completely a hyphenated word."

def test_seg_tag_metadata():
    xml = '<root>Here is a <seg type="rubric" part="I">heading segment</seg>.</root>'
    parser = get_parser()
    clean_text, meta = parser.parse(xml)
    
    start, end = find_word_range(clean_text, "heading segment")
    word_meta = get_metadata_for_word(start, end, meta)
    
    assert word_meta.get("seg_type") == "rubric"
    assert word_meta.get("seg_part") == "I"

def test_note_tag_metadata():
    xml = '<root>Text with a <note type="scribal">scribal note</note> in it.</root>'
    parser = get_parser()
    clean_text, meta = parser.parse(xml)
    
    start, end = find_word_range(clean_text, "scribal note")
    word_meta = get_metadata_for_word(start, end, meta)
    
    assert word_meta.get("note") is True
    assert word_meta.get("note_type") == "scribal"

def test_head_tag_metadata():
    xml = '<root><head>Chapter One</head></root>'
    parser = get_parser()
    clean_text, meta = parser.parse(xml)
    
    start, end = find_word_range(clean_text, "Chapter One")
    word_meta = get_metadata_for_word(start, end, meta)
    
    assert word_meta.get("head") is True

def test_subst_tag_metadata():
    xml = '<root>Hello <subst><del>country</del><add>world</add></subst>!</root>'
    parser = get_parser()
    clean_text, meta = parser.parse(xml)

    start, end = find_word_range(clean_text, "world")
    word_meta = get_metadata_for_word(start, end, meta)

    assert word_meta.get("add") is True
    assert word_meta.get("subst") is True
    
    start, end = find_word_range(clean_text, "country")
    word_meta = get_metadata_for_word(start, end, meta)

    assert word_meta.get("del") is True
    assert word_meta.get("subst") is True

# def test_subst_tag_text():
#     xml = '<root>Hello <subst><del>country</del><add>world</add></subst>!</root>'
#     parser = get_parser()
#     clean_text, meta = parser.parse(xml)

#     assert clean_text is "Hello world!"