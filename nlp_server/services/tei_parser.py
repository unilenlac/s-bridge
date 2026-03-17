import csv
import logging
import os
from typing import List, Dict, Tuple, Any, Optional

import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

# Type Aliases for clearer signatures
MetadataMap = List[Tuple[int, int, Dict[str, Any]]]
TextSegment = Tuple[str, Dict[str, Any]]
TokenData = Dict[str, Any]

class TEIParser:
    def __init__(self, abbr_file: Optional[str] = None, custom_tags: Optional[Dict[str, Any]] = None):
        self.custom_tags: Dict[str, Any] = custom_tags if custom_tags is not None else {}
        self.abbr_dict: Dict[str, str] = {}
        if abbr_file and os.path.isfile(abbr_file):
            logger.info(f"Loading abbreviation dictionary from {abbr_file}")
            with open(abbr_file, 'r', encoding='utf-8') as f:
                # Read csv. Skip header row depending on dialect or exactly if we know it
                reader = csv.reader(f, delimiter='\t')
                next(reader, None) # skip header 'abbr expan'
                for row in reader:
                    if len(row) >= 2:
                        self.abbr_dict[row[0].strip()] = row[1].strip()
            logger.info(f"Loaded {len(self.abbr_dict)} abbreviations")
        elif abbr_file:
            logger.warning(f"Abbreviation file not found: {abbr_file}")


    def parse(self, data: str) -> Tuple[str, MetadataMap]:
        """Process TEI element to extract both metadata map and clean text."""
        try:
            element = ET.fromstring(data)
        except ET.ParseError as e:
            logger.error(f"Failed to parse XML: {e}")
            raise ValueError(f"Invalid XML data provided to TEIParser: {e}")
            
        # Step 1: Clear breaks first 
        self._resolve_hyphenation_and_breaks(element)

        # Step 1.5: Remove parenthesis 
        self._remove_parenthesis(element)
        
        # Step 2: Extract text segments with their metadata
        text_segments, _ = self._extract_text_with_metadata(element)
        
        # Step 3: Build normalized text and metadata map
        clean_text, metadata_map = self._build_normalized_metadata_map(text_segments)
        
        return clean_text, metadata_map

    def _get_rightmost_text_node(self, parent: ET.Element, child_index: int) -> Tuple[ET.Element, str]:
        """Find the element and attribute ('text' or 'tail') containing the physical text just before this child."""
        if child_index > 0:
            prev = parent[child_index - 1]
            if prev.tail:
                return prev, 'tail'
            
            curr = prev
            while len(curr) > 0:
                last_child = curr[-1]
                if last_child.tail:
                    return last_child, 'tail'
                curr = last_child
            return curr, 'text'
        return parent, 'text'

    def _resolve_hyphenation_and_breaks(self, element: ET.Element) -> None:
        """Remove line/page breaks from XML, joining hyphenated words aggressively."""
        for parent in element.iter():
            for child_index in range(len(parent) - 1, -1, -1):
                child = parent[child_index]
                if child.tag in ['lb', 'pb']:
                    
                    # 1. Locate the physical text that immediately precedes the break
                    node_with_text, attr_name = self._get_rightmost_text_node(parent, child_index)
                    prior_text = getattr(node_with_text, attr_name) or ""
                    
                    if child_index > 0:
                        # Case A: Not the first child. We attach the lb's tail to the prev sibling
                        prev_sibling = parent[child_index - 1]
                        
                        if prior_text.rstrip().endswith('-'):
                            # Strip hyphen from wherever it was natively found
                            setattr(node_with_text, attr_name, prior_text.rstrip()[:-1])
                            # Merge tails tightly without space
                            prev_sibling.tail = (prev_sibling.tail or "") + (child.tail or "").lstrip()
                        else:
                            # Not hyphenated. Attach with a space
                            prev_sibling.tail = (prev_sibling.tail or "") + " " + (child.tail or "")
                    else:
                        # Case B: First child. Attach the lb's tail strictly to the parent's text
                        if prior_text.rstrip().endswith('-'):
                            # attr_name is guaranteed to be 'text' here since child_index == 0
                            parent.text = prior_text.rstrip()[:-1] + (child.tail or "").lstrip()
                        else:
                            parent.text = prior_text + " " + (child.tail or "")
                            
                    parent.remove(child)

    def _remove_parenthesis(self, element: ET.Element) -> None:
        """Remove all parentheses from text and tail of all elements."""
        for node in element.iter():
            if node.text:
                node.text = node.text.replace('(', '').replace(')', '')
            if node.tail:
                node.tail = node.tail.replace('(', '').replace(')', '')

    def _build_tag_metadata(self, element: ET.Element) -> Dict[str, Any]:
        """Build tag-specific metadata dictionary based on the element's tag configuration."""
        tag_metadata: Dict[str, Any] = {}
        if element.tag not in self.custom_tags:
            return tag_metadata

        config = self.custom_tags[element.tag]

        # 1. Static flags (e.g., {"unclear": True})
        for key, val in config.get("flags", {}).items():
            tag_metadata[key] = val

        # 2. Attributes → metadata key = {tag}_{attr}
        for attr in config.get("attributes", []):
            val = element.get(attr)
            if val:
                tag_metadata[f"{element.tag}_{attr}"] = val

        return tag_metadata

    def _process_text_chunk(
        self, 
        text: str, 
        metadata_stack: List[Dict[str, Any]], 
        pending_metadata: Dict[str, Any], 
        results: List[TextSegment]
    ) -> None:
        """Process a text chunk and append it with accumulated metadata."""
        import re
        current_metadata: Dict[str, Any] = {}
        for meta in metadata_stack:
            current_metadata.update(meta)

        #This logic handles self-closing tag such as the <unclear/> tag by applying it to the contiguous word (left or right or both)
        if pending_metadata:
            # If the upcoming text starts with a space, the empty tag was conceptually 
            # placed at the *end* of the previous word.
            if text.startswith(' ') or text.startswith('\n') or text.startswith('\t'):
                # Apply it to the last appended word if it exists
                if results:
                    last_text, last_meta = results[-1]
                    # We can't just mutate the dictionary if it's shared, so we make a copy
                    new_meta = last_meta.copy()
                    new_meta.update(pending_metadata)
                    results[-1] = (last_text, new_meta)
                else:
                    # Rare edge case: tag is at the very beginning of the document before any text, 
                    # but followed by a space. We'll just drop it or attach it to the space (which gets ignored).
                    results.append(("", pending_metadata.copy()))
            else:
                # The text does not start with a space, so the tag is conceptually
                # at the *start* of the upcoming word.
                m = re.match(r'^(\s*)(\S+)(.*)$', text, flags=re.DOTALL)
                if m:
                    spaces, word, rest = m.groups()
                    
                    if spaces:
                        results.append((spaces, current_metadata.copy()))
                    
                    word_meta = current_metadata.copy()
                    word_meta.update(pending_metadata)
                    
                    if word_meta.get('abbr'):
                        raw_abbr = word.strip()
                        if raw_abbr in self.abbr_dict:
                            word = word.replace(raw_abbr, self.abbr_dict[raw_abbr])
                            word_meta['abbr_original'] = raw_abbr
                    
                    results.append((word, word_meta))
                    
                    if rest:
                        rest_meta = current_metadata.copy()
                        if rest_meta.get('abbr'):
                            raw_abbr_rest = rest.strip()
                            if raw_abbr_rest in self.abbr_dict:
                                rest = rest.replace(raw_abbr_rest, self.abbr_dict[raw_abbr_rest])
                                rest_meta['abbr_original'] = raw_abbr_rest
                        results.append((rest, rest_meta))
                    
                    pending_metadata.clear()
                    return

            pending_metadata.clear()

        #Leaving the self closing tag logic.
        if text.strip():
            current_metadata.update(pending_metadata)
            pending_metadata.clear()
        elif pending_metadata:
            current_metadata.update(pending_metadata)

        if current_metadata.get('abbr'):
            raw_abbr = text.strip()
            if raw_abbr in self.abbr_dict:
                text = text.replace(raw_abbr, self.abbr_dict[raw_abbr])
                current_metadata['abbr_original'] = raw_abbr

        results.append((text, current_metadata))

    def _extract_text_with_metadata(
        self,
        element: ET.Element, 
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
        
        # 1. Generate Metadata
        tag_metadata = self._build_tag_metadata(element)
        if tag_metadata:
            metadata_stack.append(tag_metadata)

        # 2. Phase 1: Process .text (Inside the tag)
        if element.text:
            self._process_text_chunk(element.text, metadata_stack, pending_metadata, results)

        # 3. Phase 2: Recurse Children
        for child in element:
            self._extract_text_with_metadata(child, metadata_stack, pending_metadata, results)

        # 4. Handle Empty Tags / self-closing tag (like <unclear/> or <pb/>)
        if not len(element) and not element.text and tag_metadata:
            pending_metadata.update(tag_metadata)

        # 5. Phase 3: Tag closes, process .tail (After the tag)
        if tag_metadata:
            metadata_stack.pop()

        if element.tail:
            self._process_text_chunk(element.tail, metadata_stack, pending_metadata, results)

        return results, pending_metadata

    def _build_normalized_metadata_map(self, text_segments: List[TextSegment]) -> Tuple[str, MetadataMap]:
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

    def get_metadata_for_token(self, char_start: int, char_stop: int, metadata_map: MetadataMap) -> Dict[str, Any]:
        """Find all metadata that applies to a token's character range."""
        token_metadata: Dict[str, Any] = {}
        
        for map_start, map_stop, metadata in metadata_map:
            # Check if token overlaps with this metadata range
            if char_start < map_stop and char_stop > map_start:
                token_metadata.update(metadata)
        
        return token_metadata