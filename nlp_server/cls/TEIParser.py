import csv
import logging
import os
from typing import List, Dict, Tuple, Any, Optional, Union

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

# Type Aliases for clearer signatures
MetadataMap = List[Tuple[int, int, Dict[str, Any]]]
TextSegment = Tuple[str, Dict[str, Any]]
TokenData = Dict[str, Any]

class TEIParser:
    def __init__(self, abbr_file: Optional[str] = None):
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
        element = ET.fromstring(data)
            
        # Step 1: Clear breaks first (modifies soup in place, keeps editorial tags)
        self._resolve_hyphenation_and_breaks(element)
        
        # Step 2: Extract text segments with their metadata
        text_segments, _ = self._extract_text_with_metadata(element)
        
        # Step 3: Build normalized text and metadata map
        clean_text, metadata_map = self._build_normalized_metadata_map(text_segments)
        
        return clean_text, metadata_map

    def _resolve_hyphenation_and_breaks(self, element: ET.Element) -> None:
        """Remove line/page breaks from soup, joining hyphenated words aggressively (modifies in place)."""
        #New process with ElementTree
        for parent in element.iter():
            # Iterate backwards so that parent.remove() doesn't shift indices for preceding elements
            for child_index in range(len(parent) - 1, -1, -1):
                child = parent[child_index]
                if child.tag in ['lb', 'pb']:
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
                
    def _build_tag_metadata(self, element: ET.Element) -> Dict[str, Any]:
        """Build tag-specific metadata dictionary based on the element."""
        tag_metadata: Dict[str, Any] = {}
        
        if element.tag == 'unclear':
            tag_metadata['unclear'] = True
            if element.get('reason'):
                tag_metadata['unclear_reason'] = element.get('reason')
        
        elif element.tag == 'add':
            tag_metadata['add'] = True
            if element.get('hand'):
                tag_metadata['add_hand'] = element.get('hand')

        elif element.tag == 'del':
            tag_metadata['del'] = True
            rend = element.get('rend')
            tag_metadata['del_reason'] = rend if rend else 'other'

        elif element.tag == 'abbr':
            tag_metadata['abbr'] = True
            abbr_type = element.get('type')
            if abbr_type:
                tag_metadata['abbr_type'] = abbr_type
                
        elif element.tag == 'seg':
            seg_type = element.get('type')
            if seg_type:
                tag_metadata['seg_type'] = seg_type
            seg_part = element.get('part')
            if seg_part:
                tag_metadata['seg_part'] = seg_part
                
        elif element.tag == 'note':
            tag_metadata['is_note'] = True
            note_type = element.get('type')
            if note_type:
                tag_metadata['note_type'] = note_type
                
        elif element.tag == 'head':
            tag_metadata['is_head'] = True
            
        return tag_metadata

    def _process_text_chunk(
        self, 
        text: str, 
        metadata_stack: List[Dict[str, Any]], 
        pending_metadata: Dict[str, Any], 
        results: List[TextSegment]
    ) -> None:
        """Process a text chunk and append it with accumulated metadata."""
        current_metadata: Dict[str, Any] = {}
        for meta in metadata_stack:
            current_metadata.update(meta)

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

        # 4. Handle Empty Tags (like <unclear/> or <pb/>)
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