import argparse
import json
import logging
import csv
import os
from typing import List, Dict, Tuple, Any, Optional, Union

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag
# Removed direct CLTK import
from s_bridge.clients.analysis import AnalysisClient
from s_bridge.clients.local import LocalCltkClient
from s_bridge.clients.remote import RemoteAnalysisClient
import builtins

# Auto-answer 'y' to any interactive prompts (e.g., from CLTK downloading models)
# to prevent the script from hanging when run via automated tools or uv.
# _original_input = builtins.input
# builtins.input = lambda prompt='': 'y'
# print("Patched builtins.input to auto-answer 'y' to avoid CLTK hangs.", flush=True)

# Setup custom logger to avoid double logging issues with cltk/stanza
logger = logging.getLogger('tokenize_xml')
logger.setLevel(logging.INFO)
_ch = logging.StreamHandler()
_ch.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
logger.addHandler(_ch)
logger.propagate = False

# Type Aliases for clearer signatures
MetadataMap = List[Tuple[int, int, Dict[str, Any]]]
TextSegment = Tuple[str, Dict[str, Any]]
TokenData = Dict[str, Any]


def resolve_hyphenation_and_breaks(soup: BeautifulSoup) -> None:
    """Remove line/page breaks from soup, joining hyphenated words aggressively (modifies in place)."""
    
    # Process all <lb> and <pb> tags
    for break_tag in soup.find_all(['lb', 'pb']):
        is_hyphenated = False
        
        # A. Inspect preceding text logic
        prev_node = break_tag.previous_sibling
        # Look backwards to find actual text if there's an enclosing tag like <unclear>
        while prev_node and not isinstance(prev_node, NavigableString) and getattr(prev_node, 'name', None) is not None:
            if list(prev_node.children):
                prev_node = list(prev_node.children)[-1]
            else:
                break
                
        if isinstance(prev_node, NavigableString):
            text = str(prev_node)
            clean_text = text.rstrip()
            if clean_text.endswith('-'):
                is_hyphenated = True
                # Delete the physical hyphen
                text = clean_text[:-1]
                prev_node.replace_with(NavigableString(text))
                
        if is_hyphenated:
            # B. Clean the following text (remove leading whitespace because we are merging)
            next_node = break_tag.next_sibling
            while next_node and not isinstance(next_node, NavigableString) and getattr(next_node, 'name', None) is not None:
                if list(next_node.children):
                    next_node = list(next_node.children)[0]
                else:
                    break
                    
            if isinstance(next_node, NavigableString):
                text = str(next_node)
                text = text.lstrip()
                next_node.replace_with(NavigableString(text))
            
            # C. Destroy the break tag entirely so words merge without spaces
            break_tag.decompose()
        else:
            # Not a hyphenated word, just replace the break block with a space
            break_tag.replace_with(NavigableString(' '))


def extract_text_with_metadata(
    element: Union[Tag, NavigableString, BeautifulSoup], 
    abbr_dict: Dict[str, str],
    metadata_stack: Optional[List[Dict[str, Any]]] = None, 
    pending_metadata: Optional[Dict[str, Any]] = None, 
    results: Optional[List[TextSegment]] = None
) -> Tuple[List[TextSegment], Dict[str, Any]]:
    """
    Extract text segments with their associated metadata.
    Returns list of (text_segment, metadata_dict) tuples.
    """
    if metadata_stack is None:
        metadata_stack = []
    if pending_metadata is None:
        pending_metadata = {}
    if results is None:
        results = []
    
    if isinstance(element, NavigableString):
        text = str(element)
        if text:  # Add all text including structural whitespace
            # Copy current metadata stack
            current_metadata: Dict[str, Any] = {}
            for meta in metadata_stack:
                current_metadata.update(meta)
                
            if text.strip():
                current_metadata.update(pending_metadata)
                pending_metadata.clear()
            elif pending_metadata:
                # Still attach pending metadata to these spaces, but don't clear it
                current_metadata.update(pending_metadata)
                
            if current_metadata.get('abbr'):
                raw_abbr = text.strip()
                if raw_abbr in abbr_dict:
                    # Expand the abbreviation text
                    text = text.replace(raw_abbr, abbr_dict[raw_abbr])
                    current_metadata['abbr_original'] = raw_abbr
            
            results.append((text, current_metadata))
        return results, pending_metadata
    
    if isinstance(element, (Tag, BeautifulSoup)):
        # Build metadata for this tag
        tag_metadata: Dict[str, Any] = {}
        
        if getattr(element, 'name', None) == 'unclear':
            tag_metadata['unclear'] = True
            if element.get('reason'):
                tag_metadata['unclear_reason'] = element.get('reason')
        
        if getattr(element, 'name', None) == 'add':
            tag_metadata['add'] = True
            if element.get('hand'):
                tag_metadata['add_hand'] = element.get('hand')

        if getattr(element, 'name', None) == 'del':
            tag_metadata['del'] = True
            rend = element.get('rend')
            tag_metadata['del_reason'] = rend if rend else 'other'

        if getattr(element, 'name', None) == 'abbr':
            # Abbreviation expansion is handled at the text node level,
            # but we record that we are inside an abbr tag
            tag_metadata['abbr'] = True
            abbr_type = element.get('type')
            if abbr_type:
                tag_metadata['abbr_type'] = abbr_type
                
            # For elongation later: check text inside this specific tag
            # If the entire element has a single text string, we can intercept it
            # But the most robust way in BS4 recursive extraction is to handle it
            # right before the text is appended if 'abbr' is in the stack.
        
        # Push metadata onto stack if this tag has any
        if tag_metadata:
            metadata_stack.append(tag_metadata)
        
        has_children = False
        # Process children
        for child in getattr(element, 'children', []):
            has_children = True
            extract_text_with_metadata(child, abbr_dict, metadata_stack, pending_metadata, results)
        
        # If the tag is empty but has metadata, apply it to pending_metadata
        # so it attaches to the next valid text node
        if not has_children and tag_metadata:
            pending_metadata.update(tag_metadata)
            
        # Pop metadata from stack
        if tag_metadata:
            metadata_stack.pop()
    
    return results, pending_metadata


def build_normalized_metadata_map(text_segments: List[TextSegment]) -> Tuple[str, MetadataMap]:
    """
    Build a character position map for normalized text.
    Handles words that are split across text segments without whitespace.
    """
    normalized_parts: List[str] = []
    metadata_map: MetadataMap = []
    char_offset = 0
    
    raw_chars = []
    raw_meta = []
    for text, metadata in text_segments:
        for ch in text:
            raw_chars.append(ch)
            raw_meta.append(metadata)
            
    current_word_chars = []
    current_word_metas = []
    
    def process_word():
        nonlocal char_offset
        if not current_word_chars:
            return
        word_str = "".join(current_word_chars)
        word_str = word_str.strip("-")
        if word_str:
            if normalized_parts:
                char_offset += 1  # space
            
            start_offset = char_offset
            normalized_parts.append(word_str)
            char_offset += len(word_str)
            end_offset = char_offset
            
            merged_meta = {}
            for m in current_word_metas:
                if m:
                    merged_meta.update(m)
            
            if merged_meta:
                metadata_map.append((start_offset, end_offset, merged_meta))
                
        current_word_chars.clear()
        current_word_metas.clear()

    for ch, meta in zip(raw_chars, raw_meta):
        if ch.isspace():
            process_word()
        else:
            current_word_chars.append(ch)
            current_word_metas.append(meta)
            
    process_word()
    
    normalized_text = ' '.join(normalized_parts)
    return normalized_text, metadata_map


def get_metadata_for_token(char_start: int, char_stop: int, metadata_map: MetadataMap) -> Dict[str, Any]:
    """Find all metadata that applies to a token's character range."""
    token_metadata: Dict[str, Any] = {}
    
    for map_start, map_stop, metadata in metadata_map:
        # Check if token overlaps with this metadata range
        if char_start < map_stop and char_stop > map_start:
            token_metadata.update(metadata)
    
    return token_metadata


def build_collatex_tokens(json_tokens: List[Dict[str, Any]], metadata_map: MetadataMap, n_format: str = "lemma+pos") -> List[TokenData]:
    """
    Applies editorial metadata and string formatting to tokens returned by the AnalysisClient.
    The `json_tokens` should be dictionaries matching the token output specification.
    """
    collatex_payloads: List[TokenData] = []
    
    # We need to track the character offsets to apply the metadata map correctly.
    # We rebuild the index based on string lengths.
    current_char_offset = 0
    
    for token in json_tokens:
        # Create a copy so we don't modify the client's output directly
        token_data = dict(token)
        t_val = token_data.get("t", "")
        
        # Calculate char offsets for editorial metadata matching
        char_start = current_char_offset
        char_stop = current_char_offset + len(t_val)
        
        # Increment offset for next token + space (assuming single space split)
        # Note: This is an approximation. If exact character offsets are needed,
        # the client should ideally return index_char_start and index_char_stop.
        current_char_offset += len(t_val) + 1 
        
        # Apply editorial metadata if offset matches
        editorial_metadata = get_metadata_for_token(char_start, char_stop, metadata_map)
        token_data.update(editorial_metadata)
            
        if "editorial" in getattr(n_format, "split", lambda x: [])('+'):
            ed_tags = []
            for tag in ["unclear", "add", "del", "abbr"]:
                if editorial_metadata.get(tag):
                    ed_tags.append(tag)
            if ed_tags:
                # Append strictly at the end of whatever n_val currently is
                token_data["n"] = f"{token_data.get('n', '')}+{'+'.join(ed_tags)}"
        
        collatex_payloads.append(token_data)
        
    return collatex_payloads


def extract_normalized_text_and_metadata(soup: BeautifulSoup, abbr_dict: Dict[str, str]) -> Tuple[str, MetadataMap]:
    """Process TEI soup to extract both metadata map and clean text."""
    # Step 1: Clear breaks first (modifies soup in place, keeps editorial tags)
    resolve_hyphenation_and_breaks(soup)
    
    # Step 2: Extract text segments with their metadata (after clearing breaks)
    text_segments, _ = extract_text_with_metadata(soup, abbr_dict)
    
    # Step 3: Build normalized text and metadata map
    clean_text, metadata_map = build_normalized_metadata_map(text_segments)
    
    return clean_text, metadata_map


class XMLTokenizer:
    """Class to manage the NLP pipeline and XML parsing together."""
    def __init__(self, analysis_client: AnalysisClient, normalization: str = "lemma+pos", abbr_file: Optional[str] = None):
        self.analysis_client = analysis_client
        self.normalization = normalization
        
        # Load abbreviations lookup
        self.abbr_dict: Dict[str, str] = {}
        if abbr_file and os.path.isfile(abbr_file):
            logger.info(f"Loading abbreviations from {abbr_file}")
            with open(abbr_file, 'r', encoding='utf-8') as f:
                # Read csv. Skip header row depending on dialect or exactly if we know it
                reader = csv.reader(f, delimiter='\t')
                next(reader, None) # skip header 'abbr  expan'
                for row in reader:
                    if len(row) >= 2:
                        self.abbr_dict[row[0].strip()] = row[1].strip()
            logger.info(f"Successfully loaded {len(self.abbr_dict)} abbreviations.")
        elif abbr_file:
             logger.warning(f"Abbreviation file '{abbr_file}' was specified but not found. Skipping abbreviation expansion.")

    def tokenize_file(self, file_path: str) -> Union[List[TokenData], Dict[str, Any]]:
        """Reads an XML file and tokenizes its text according to the internal logic."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        soup = BeautifulSoup(content, features="xml")
        
        # Check if there are witness tags
        witnesses = soup.find_all('witness')
        if witnesses:
            print(f"Found {len(witnesses)} witnesses")
            collatex_payload = {"witnesses": []}
            for w in witnesses:
                wid = w.get('id', 'unknown')
                clean_cltk_string, metadata_map = extract_normalized_text_and_metadata(w, self.abbr_dict)
                if not clean_cltk_string.strip():
                    continue
                
                json_tokens = self.analysis_client.analyze_text(clean_cltk_string)
                tokens = build_collatex_tokens(json_tokens, metadata_map, n_format=self.normalization)
                
                collatex_payload["witnesses"].append({
                    "id": wid,
                    "tokens": tokens
                })
            return collatex_payload
        else:
            # Standard single document TEI XML parsing
            clean_cltk_string, metadata_map = extract_normalized_text_and_metadata(soup, self.abbr_dict)
            
            if not clean_cltk_string.strip():
                raise ValueError(f"Input text in {file_path} is empty or parsing failed.")
            
            json_tokens = self.analysis_client.analyze_text(clean_cltk_string)
            collatex_payloads = build_collatex_tokens(json_tokens, metadata_map, n_format=self.normalization)
            
            return collatex_payloads


def validate_file_path(path: str) -> str:
    import os
    if not os.path.isfile(path):
        raise argparse.ArgumentTypeError(f"File '{path}' does not exist.")
    return path

def main() -> None:
    parser = argparse.ArgumentParser(description="Parse XML file and generate CollateX token payload.")
    parser.add_argument("input_file", type=validate_file_path, help="Path to the .xml file to parse.")
    parser.add_argument("--output", "-o", help="Optional output JSON file path.", default=None)
    parser.add_argument(
        "--normalization", "-n", 
        choices=[
            "lemma", 
            "lemma+pos", 
            "lemma+pos+cgn", 
            "lemma+pos+editorial", 
            "lemma+pos+cgn+editorial", 
            "original"
        ], 
        default="lemma+pos", 
        help="Strictness configuration for the CollateX token 'n' field (default: lemma+pos)"
    )
    parser.add_argument("--remote-host", help="Hostname of the NLP server (if using remote)", default=None)
    parser.add_argument("--remote-port", type=int, help="Port of the NLP server (if using remote)", default=8000)
    parser.add_argument("--abbr-file", help="Path to TSV/CSV dictionary for <abbr> elongation.", default="utils/abbr.csv")
    args = parser.parse_args()
    
    try:
        if args.remote_host:
            logger.info(f"Connecting to remote NLP server at {args.remote_host}:{args.remote_port}")
            client = RemoteAnalysisClient(host=args.remote_host, port=args.remote_port)
        else:
            logger.info("Initializing Local NLP pipeline (this may take a moment)...")
            client = LocalCltkClient(n_format=args.normalization)
            
        tokenizer = XMLTokenizer(analysis_client=client, normalization=args.normalization, abbr_file=args.abbr_file)
        
        logger.info(f"Now processing file: {args.input_file}")
        tokens = tokenizer.tokenize_file(args.input_file)
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(tokens, f, indent=2, ensure_ascii=False)
                
            # Calculate total tokens properly if it's the witnesses dict
            if isinstance(tokens, dict) and "witnesses" in tokens:
                total_tokens = sum(len(w.get("tokens", [])) for w in tokens["witnesses"])
            else:
                total_tokens = len(tokens)
                
            logger.info(f"Successfully saved {total_tokens} tokens to {args.output}")
        else:
            print(json.dumps(tokens, indent=2, ensure_ascii=False))
            
    except Exception as e:
        logger.error(f"An error occurred while processing the file: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
