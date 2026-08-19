from typing import List, Optional
import re

from core.interfaces import Processor, Parser
from models.tokenization import Token
from helpers.helpers import extract_body_content, extract_tei_header_metadata


class RawStrategyConverter:
    def __init__(self, proc: Processor):
        self.processor = proc

    def run(
        self,
        data: str,
        normalization: str = "text",
        filter_del: bool = False,
        doc_title: Optional[str] = None,
    ) -> List[Token]:
        import xml.etree.ElementTree as ET

        if doc_title is None and ("<titleStmt" in data or "<title" in data):
            meta = extract_tei_header_metadata(data)
            doc_title = meta.get("doc_title")

        body_content = extract_body_content(data)

        try:
            # Attempt to parse as XML to isolate body and avoid header noise
            root = ET.fromstring(body_content)
            data = "".join(root.itertext())
        except Exception:
            # If parsing fails, fall back to regex tag-stripping to strip any XML remains
            clean_text = re.sub(r"<[^>]*>", "", body_content)
            # Strip any trailing unclosed tag at the very end of the string
            data = re.sub(r"<[^>]*$", "", clean_text)

        tokens: List[Token] = self.processor.process(data, normalization=normalization)
        if doc_title:
            for token in tokens:
                token.doc_title = doc_title
        return tokens


class EnrichedStrategyConverter:
    def __init__(self, proc: Processor, parser: Parser):
        self.processor = proc
        self.parser = parser

    def run(
        self,
        data: str,
        normalization: str = "lemma",
        filter_del: bool = True,
        doc_title: Optional[str] = None,
    ) -> List[Token]:
        # 0. Detect title from header if not explicitly provided
        if doc_title is None and ("<titleStmt" in data or "<title" in data):
            meta = extract_tei_header_metadata(data)
            doc_title = meta.get("doc_title")

        # 1. Extract clean text and offset metadata using the TEI Parser
        clean_text, metadata_map = self.parser.parse(data)

        # 2. Process the raw string into tokens using our generic Processor
        raw_tokens: List[Token] = self.processor.process(
            clean_text, normalization=normalization
        )

        # 3. Marry the TEI Metadata with the NLP Tokens based on character offsets
        enriched_tokens = []
        current_char_offset = 0

        for token in raw_tokens:
            if (
                getattr(token, "char_start", None) is not None
                and getattr(token, "char_stop", None) is not None
            ):
                char_start = token.char_start
                char_stop = token.char_stop
                current_char_offset = char_stop + 1
            else:
                char_start = current_char_offset
                char_stop = current_char_offset + len(token.original)
                current_char_offset += len(token.original) + 1

            # Get matching metadata
            editorial_metadata = self.parser.get_metadata_for_token(
                char_start, char_stop, metadata_map
            )

            # Reconstruct the Token dictionary to inject the metadata
            token_dict = token.model_dump(by_alias=False, exclude_none=True)
            token_dict.update(editorial_metadata)
            if doc_title:
                token_dict["doc_title"] = doc_title

            # Re-instantiate the completely enriched Token

            # THE FILTERING LOGIC
            if filter_del and editorial_metadata.get("del") is True:
                continue  # Skip this token entirely

            enriched_token = Token(**token_dict)
            enriched_tokens.append(enriched_token)

        return enriched_tokens
