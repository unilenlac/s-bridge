import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import xml.etree.ElementTree as ET
from nlp_server.services.tei_parser import TEIParser

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
    from nlp_server.core.config import Settings
    tags = Settings().load_tag_dictionary()
    return TEIParser(custom_tags=tags)

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
    assert word_meta.get("del_rend") == "strike"

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
    
    assert word_meta.get("seg") is True
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

# --- Dynamic Tag Configuration Tests ---

def test_custom_tag_with_flags_and_attributes():
    """Custom tag defined via config produces correct metadata."""
    custom_tags = {
        "highlight": {
            "flags": {"highlight": True},
            "attributes": ["type"],
        }
    }
    parser = TEIParser(custom_tags=custom_tags)
    xml = '<root>A <highlight type="yellow">marked</highlight> word.</root>'
    clean_text, meta = parser.parse(xml)

    assert clean_text == "A marked word."
    start, end = find_word_range(clean_text, "marked")
    word_meta = get_metadata_for_word(start, end, meta)
    assert word_meta.get("highlight") is True
    assert word_meta.get("highlight_type") == "yellow"

def test_custom_tag_self_closing():
    """Self-closing custom tag applies metadata to the neighboring word via pending_metadata."""
    custom_tags = {
        "damage": {
            "flags": {"damage": True},
            "attributes": ["extent"],
        }
    }
    parser = TEIParser(custom_tags=custom_tags)
    xml = '<root>Some <damage extent="2 chars"/>broken text.</root>'
    clean_text, meta = parser.parse(xml)

    assert clean_text == "Some broken text."
    start, end = find_word_range(clean_text, "broken")
    word_meta = get_metadata_for_word(start, end, meta)
    assert word_meta.get("damage") is True
    assert word_meta.get("damage_extent") == "2 chars"

# removed tests for attribute_list, attribute_map, and defaults as features were removed.

def test_default_enlac_tags_backward_compat():
    """Verify that get_parser() (loading default JSON) produces expected ENLAC behavior."""
    parser = get_parser()

    # unclear
    xml = '<root>An <unclear reason="illegible"/>obscure text.</root>'
    clean_text, meta = parser.parse(xml)
    start, end = find_word_range(clean_text, "obscure")
    assert get_metadata_for_word(start, end, meta).get("unclear") is True
    assert get_metadata_for_word(start, end, meta).get("unclear_reason") == "illegible"

    # add
    xml = '<root>The editor <add hand="scribe1">added</add> this.</root>'
    clean_text, meta = parser.parse(xml)
    start, end = find_word_range(clean_text, "added")
    assert get_metadata_for_word(start, end, meta).get("add") is True
    assert get_metadata_for_word(start, end, meta).get("add_hand") == "scribe1"

    # del
    xml = '<root>A <del rend="strike">deleted</del> word.</root>'
    clean_text, meta = parser.parse(xml)
    start, end = find_word_range(clean_text, "deleted")
    assert get_metadata_for_word(start, end, meta).get("del") is True
    assert get_metadata_for_word(start, end, meta).get("del_rend") == "strike"

    # seg
    xml = '<root>A <seg type="rubric" part="I">segment</seg>.</root>'
    clean_text, meta = parser.parse(xml)
    start, end = find_word_range(clean_text, "segment")
    assert get_metadata_for_word(start, end, meta).get("seg") is True
    assert get_metadata_for_word(start, end, meta).get("seg_type") == "rubric"
    assert get_metadata_for_word(start, end, meta).get("seg_part") == "I"

    # head
    xml = '<root><head>Title</head></root>'
    clean_text, meta = parser.parse(xml)
    start, end = find_word_range(clean_text, "Title")
    assert get_metadata_for_word(start, end, meta).get("head") is True

    # subst
    xml = '<root><subst><del>old</del><add>new</add></subst></root>'
    clean_text, meta = parser.parse(xml)
    start, end = find_word_range(clean_text, "new")
    word_meta = get_metadata_for_word(start, end, meta)
    assert word_meta.get("subst") is True
    assert word_meta.get("add") is True

# --- Settings / Tag Config Loading Tests ---

def test_load_tag_dictionary_default():
    """load_tag_dictionary() returns the default ENLAC tags when tag_config is unset."""
    from nlp_server.core.config import Settings
    s = Settings(tag_config=None)
    result = s.load_tag_dictionary()
    assert isinstance(result, dict)
    assert "unclear" in result
    assert result["unclear"]["flags"] == {"unclear": True}

def test_load_tag_dictionary_valid_file(tmp_path):
    """load_tag_dictionary() returns the parsed dict from a valid JSON file."""
    import json
    from nlp_server.core.config import Settings

    tag_data = {
        "highlight": {"flags": {"highlight": True}, "attributes": ["type"]}
    }
    tag_file = tmp_path / "tags.json"
    tag_file.write_text(json.dumps(tag_data), encoding="utf-8")

    s = Settings(tag_config=str(tag_file))
    result = s.load_tag_dictionary()
    assert result == tag_data

def test_load_tag_dictionary_file_not_found():
    """load_tag_dictionary() raises FileNotFoundError on a missing file."""
    from nlp_server.core.config import Settings
    import pytest

    s = Settings(tag_config="/nonexistent/path/tags.json")
    with pytest.raises(FileNotFoundError, match="Tag config file not found"):
        s.load_tag_dictionary()

def test_load_tag_dictionary_invalid_json(tmp_path):
    """load_tag_dictionary() raises ValueError on malformed JSON."""
    from nlp_server.core.config import Settings
    import pytest

    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{not valid json", encoding="utf-8")

    s = Settings(tag_config=str(bad_file))
    with pytest.raises(ValueError, match="invalid JSON"):
        s.load_tag_dictionary()