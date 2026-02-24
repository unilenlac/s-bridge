import argparse
import json
import logging
from typing import List, Dict, Tuple, Any, Optional, Union

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag
from cltk import NLP
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
    """Remove line/page breaks from soup (modifies in place)."""
    # 1. Resolve hyphenated breaks (<lb break="no"/>)
    for lb in soup.find_all('lb', attrs={'break': 'no'}):
        
        # A. Clean the preceding text and delete the physical hyphen
        prev_node = lb.previous_sibling
        # Look backwards to find actual text if there's an enclosing tag like <unclear>
        while prev_node and not isinstance(prev_node, NavigableString) and getattr(prev_node, 'name', None) is not None:
            # Simple assumption: if the previous sibling is a tag, the text we want to modify is inside it
            if list(prev_node.children):
                prev_node = list(prev_node.children)[-1]
            else:
                break
                
        if isinstance(prev_node, NavigableString):
            text = str(prev_node)
            text = text.rstrip()
            if text.endswith('-'):
                text = text[:-1]
            prev_node.replace_with(NavigableString(text))
        
        # B. Clean the following text (remove leading whitespace)
        next_node = lb.next_sibling
        while next_node and not isinstance(next_node, NavigableString) and getattr(next_node, 'name', None) is not None:
            if list(next_node.children):
                next_node = list(next_node.children)[0]
            else:
                break
                
        if isinstance(next_node, NavigableString):
            text = str(next_node)
            text = text.lstrip()
            next_node.replace_with(NavigableString(text))
        
        # C. Destroy the <lb> tag
        lb.decompose()
    
    # 2. Handle normal <lb> and <pb> tags - replace with space
    for break_tag in soup.find_all(['lb', 'pb']):
        break_tag.replace_with(NavigableString(' '))


def extract_text_with_metadata(
    element: Union[Tag, NavigableString, BeautifulSoup], 
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
            tag_metadata['abbr'] = True
            abbr_type = element.get('type')
            if abbr_type:
                tag_metadata['abbr_type'] = abbr_type
        
        # Push metadata onto stack if this tag has any
        if tag_metadata:
            metadata_stack.append(tag_metadata)
        
        has_children = False
        # Process children
        for child in getattr(element, 'children', []):
            has_children = True
            extract_text_with_metadata(child, metadata_stack, pending_metadata, results)
        
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


def build_collatex_tokens(doc: Any, metadata_map: MetadataMap, n_format: str = "lemma+pos") -> List[TokenData]:
    """
    Creates tokens suitable for CollateX from a CLTK Doc object and metadata map.
    """
    collatex_payloads: List[TokenData] = []
    
    for word in doc.words:
        pos_tag = word.upos.tag if word.upos else "UNKNOWN"
        
        if pos_tag == "PUNCT":
            if collatex_payloads:
                collatex_payloads[-1]["original"] += word.string
            continue
        
        feat_obj = getattr(word, 'features', None)
        feats_dict = {}
        if feat_obj and hasattr(feat_obj, 'features'):
             feats_dict = {tag.key: tag.value for tag in getattr(feat_obj, 'features', [])}
        
        lemma = word.lemma if getattr(word, 'lemma', None) is not None else word.string
        
        if n_format == "original":
            n_val = word.string
        elif n_format == "lemma":
            n_val = lemma
        else: # Handle all + configurations
            parts = n_format.split('+')
            n_components = []
            
            if "lemma" in parts:
                n_components.append(lemma)
            elif "original" in parts:
                n_components.append(word.string)
                
            if "pos" in parts:
                n_components.append(pos_tag)
                
            if "cgn" in parts:
                case = feats_dict.get("Case")
                gender = feats_dict.get("Gender")
                num = feats_dict.get("Number")
                if case: n_components.append(case)
                if gender: n_components.append(gender)
                if num: n_components.append(num)
                
            n_val = "+".join(n_components)
        
        token_data: TokenData = {
            "t": word.string,
            "n": n_val,
            "original": word.string,
            "lem": lemma,
            "pos": pos_tag,
            "case": feats_dict.get("Case"),
            "gender": feats_dict.get("Gender"),
            "num": feats_dict.get("Number")
        }
        
        # Word object in cltk usually has index_char_start and index_char_stop
        # Only assign editorial metadata if we have character offsets for the word
        start = getattr(word, 'index_char_start', None)
        stop = getattr(word, 'index_char_stop', None)
        
        if start is not None and stop is not None:
            editorial_metadata = get_metadata_for_token(start, stop, metadata_map)
            token_data.update(editorial_metadata)
            
            if "editorial" in getattr(n_format, "split", lambda x: [])('+'):
                ed_tags = []
                for tag in ["unclear", "add", "del", "abbr"]:
                    if editorial_metadata.get(tag):
                        ed_tags.append(tag)
                if ed_tags:
                    # Append strictly at the end of whatever n_val currently is
                    token_data["n"] = f"{token_data['n']}+{'+'.join(ed_tags)}"
        
        collatex_payloads.append(token_data)
    
    return collatex_payloads


def extract_normalized_text_and_metadata(soup: BeautifulSoup) -> Tuple[str, MetadataMap]:
    """Process TEI soup to extract both metadata map and clean text."""
    # Step 1: Clear breaks first (modifies soup in place, keeps editorial tags)
    resolve_hyphenation_and_breaks(soup)
    
    # Step 2: Extract text segments with their metadata (after clearing breaks)
    text_segments, _ = extract_text_with_metadata(soup)
    
    # Step 3: Build normalized text and metadata map
    clean_text, metadata_map = build_normalized_metadata_map(text_segments)
    
    return clean_text, metadata_map


class XMLTokenizer:
    """Class to manage the NLP pipeline and XML parsing together."""
    def __init__(self, nlp_backend: str = "stanza", lang: str = "grc", normalization: str = "lemma+pos"):
        # Suppress output from CLTK during initialization
        logging.getLogger('cltk').setLevel(logging.ERROR)
        logging.getLogger('stanza').setLevel(logging.ERROR)
        self.nlp = NLP(lang, backend=nlp_backend, suppress_banner=True)
        self.normalization = normalization

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
                clean_cltk_string, metadata_map = extract_normalized_text_and_metadata(w)
                if not clean_cltk_string.strip():
                    continue
                
                doc = self.nlp.analyze(clean_cltk_string)
                tokens = build_collatex_tokens(doc, metadata_map, n_format=self.normalization)
                
                collatex_payload["witnesses"].append({
                    "id": wid,
                    "tokens": tokens
                })
            return collatex_payload
        else:
            # Standard single document TEI XML parsing
            clean_cltk_string, metadata_map = extract_normalized_text_and_metadata(soup)
            
            if not clean_cltk_string.strip():
                raise ValueError(f"Input text in {file_path} is empty or parsing failed.")
            
            doc = self.nlp.analyze(clean_cltk_string)
            collatex_payloads = build_collatex_tokens(doc, metadata_map, n_format=self.normalization)
            
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
    args = parser.parse_args()
    
    try:
        logger.info("Initializing NLP pipeline (this may take a moment)..., for optimization")
        tokenizer = XMLTokenizer(normalization=args.normalization)
        
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
