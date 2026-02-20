from cltk import NLP
import requests
from bs4 import BeautifulSoup
import json
from bs4.element import NavigableString, Tag
import re


def clear_breaks(soup):
    """Remove line/page breaks from soup (modifies in place)."""
    # 1. Resolve hyphenated breaks (<lb break="no"/>)
    for lb in soup.find_all('lb', attrs={'break': 'no'}):
        
        # A. Clean the preceding text and delete the physical hyphen
        prev_node = lb.previous_sibling
        if prev_node and prev_node.name is None:  # Ensures it's a text node
            text = str(prev_node)
            # Remove trailing whitespace and hyphen
            text = text.rstrip()
            if text.endswith('-'):
                text = text[:-1]
            prev_node.replace_with(text)
        
        # B. Clean the following text (remove leading whitespace)
        next_node = lb.next_sibling
        if next_node and next_node.name is None:
            text = str(next_node)
            text = text.lstrip()
            next_node.replace_with(text)
        
        # C. Destroy the <lb> tag
        lb.decompose()
    
    # 2. Handle normal <lb> and <pb> tags - replace with space
    for break_tag in soup.find_all(['lb', 'pb']):
        break_tag.replace_with(' ')


def extract_text_with_metadata(element, metadata_stack=None, results=None):
    """
    Extract text segments with their associated metadata.
    Returns list of (text_segment, metadata_dict) tuples.
    """
    if metadata_stack is None:
        metadata_stack = []
    if results is None:
        results = []
    
    if isinstance(element, NavigableString):
        text = str(element)
        if text.strip():  # Only add non-empty text
            # Copy current metadata stack
            current_metadata = {}
            for meta in metadata_stack:
                current_metadata.update(meta)
            results.append((text, current_metadata))
        return results
    
    if isinstance(element, Tag):
        # Build metadata for this tag
        tag_metadata = {}
        
        if element.name == 'unclear':
            tag_metadata['unclear'] = True
            if element.get('reason'):
                tag_metadata['unclear_reason'] = element.get('reason')
        
        if element.name == 'add':
            tag_metadata['add'] = True
            if element.get('hand'):
                tag_metadata['add_hand'] = element.get('hand')
        
        # Push metadata onto stack if this tag has any
        if tag_metadata:
            metadata_stack.append(tag_metadata)
        
        # Process children
        for child in element.children:
            extract_text_with_metadata(child, metadata_stack, results)
        
        # Pop metadata from stack
        if tag_metadata:
            metadata_stack.pop()
    
    return results


def build_normalized_metadata_map(text_segments):
    """
    Build a character position map for normalized text.
    text_segments: list of (text, metadata) tuples
    Returns: (normalized_text, metadata_map)
    """
    normalized_parts = []
    metadata_map = []
    char_offset = 0
    
    for text, metadata in text_segments:
        # Normalize this segment's whitespace
        words = text.split()
        
        for i, word in enumerate(words):
            # Add space before word (except first word overall)
            if normalized_parts:
                char_offset += 1  # space
            
            start_offset = char_offset
            word = word.strip("-")
            if word:
                normalized_parts.append(word)
            char_offset += len(word)
            end_offset = char_offset
            
            # Record metadata for this word if it has any
            if metadata:
                metadata_map.append((start_offset, end_offset, metadata.copy()))
    
    normalized_text = ' '.join(normalized_parts)
    return normalized_text, metadata_map


def get_metadata_for_token(char_start, char_stop, metadata_map):
    """Find all metadata that applies to a token's character range."""
    token_metadata = {}
    
    for map_start, map_stop, metadata in metadata_map:
        # Check if token overlaps with this metadata range
        if char_start < map_stop and char_stop > map_start:
            token_metadata.update(metadata)
    
    return token_metadata


def collatex_token_from_doc(doc, metadata_map):
    collatex_payloads = []
    
    for word in doc.words:
        pos_tag = word.upos.tag if word.upos else "UNKNOWN"
        
        if pos_tag == "PUNCT":
            if collatex_payloads:
                collatex_payloads[-1]["original"] += word.string
            continue
        
        feats_dict = {tag.key: tag.value for tag in word.features.features} if getattr(word, 'features', None) else {}
        
        token_data = {
            "t": word.string,
            "n": f"{word.lemma}+{pos_tag}",
            "original": word.string,
            "lem": word.lemma,
            "pos": pos_tag,
            "case": feats_dict.get("Case"),
            "gender": feats_dict.get("Gender"),
            "num": feats_dict.get("Number")
        }
        
        editorial_metadata = get_metadata_for_token(word.index_char_start, word.index_char_stop, metadata_map)
        token_data.update(editorial_metadata)
        
        collatex_payloads.append(token_data)
    
    return collatex_payloads


def process_tei_to_collatex(soup):
    """Process TEI soup to extract both metadata map and clean text."""
    # Step 1: Clear breaks first (modifies soup in place, keeps editorial tags)
    clear_breaks(soup)
    
    # Step 2: Extract text segments with their metadata (after clearing breaks)
    text_segments = extract_text_with_metadata(soup)
    
    # Step 3: Build normalized text and metadata map
    clean_text, metadata_map = build_normalized_metadata_map(text_segments)
    
    return clean_text, metadata_map


def main():
    nlp = NLP("grc", backend="stanza", suppress_banner=True)
    
    url: str = "http://ftsr-dev.unil.ch:8000/api/dts/v1/document"
    params: dict[str, str] = {"resource": "athous-iviron-450"}
    headers: dict[str, str] = {"accept": "application/xml"}
    response: requests.Response = requests.get(url, params=params, headers=headers)
    
    text_to_process: str = response.text

    print(text_to_process)
    
    # Use the 'xml' parser specifically for TEI
    soup = BeautifulSoup(text_to_process, features="xml")
    
    clean_cltk_string, metadata_map = process_tei_to_collatex(soup)
    
    doc = nlp.analyze(clean_cltk_string)
    
    collatex_payloads = collatex_token_from_doc(doc, metadata_map)
    
    # Print a formatted sample
    print(json.dumps(collatex_payloads, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()

 # {
 #    "t": "λὸς",
 #    "n": "πόος+NOUN",
 #    "original": "λὸς",
 #    "lem": "πόος",
 #    "pos": "NOUN",
 #    "case": "Nom",
 #    "gender": "Masc",
 #    "num": "Sing",
 #    "add": true,
 #    "add_hand": "manus1"
 #  },