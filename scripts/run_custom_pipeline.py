#!/usr/bin/env python3
"""
Custom Pipeline Script for s-bridge

Runs the NLP tokenization and CollateX alignment pipeline on inline manuscript texts
defined directly in Python, bypassing external DTS endpoint fetching.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# Ensure project root is in the Python search path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import httpx

from core.config import Settings
from api.dependencies import ProcessingOptions
from services.tei_parser import TEIParser
from services.processors import ClassicalProcessor, ModernProcessor, RawProcessor
from services.converters import EnrichedStrategyConverter, RawStrategyConverter
from clients.collatex_client import CollatexClient
from models.tokenization import CollatexResponse, CollatexWitness, Token

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("custom_pipeline")


# ==============================================================================
# MANUSCRIPT INPUT DEFINITION
# Edit or replace these manuscripts directly in the script to test custom inputs!
# Content can be plain text strings OR TEI XML strings.
# ==============================================================================
MANUSCRIPTS: Dict[str, str] = {
    "Codex_A": "in principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbum",
    "Codex_B": "in principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbum",
    "Codex_C": "in principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbumin principio erat verbum et verbum erat apud deum et deus erat verbum",
}


def get_processor(processor_type: str, language: str):
    """Instantiates the selected NLP processor."""
    if processor_type == "raw":
        logger.info("Using RawProcessor (whitespace splitting)")
        return RawProcessor()
    elif processor_type == "classical":
        logger.info(f"Initializing ClassicalProcessor with CLTK for language: {language}...")
        from cltk import NLP
        cltk_nlp = NLP(language, backend="stanza", suppress_banner=True)
        return ClassicalProcessor(cltk_nlp)
    elif processor_type == "modern":
        logger.info(f"Initializing ModernProcessor with Stanza for language: {language}...")
        import stanza
        pipeline = stanza.Pipeline(language, processors="tokenize,pos,lemma", verbose=False)
        return ModernProcessor(pipeline)
    else:
        raise ValueError(f"Unknown processor type: {processor_type}")


def tokenize_manuscript(
    siglum: str,
    text: str,
    processor,
    normalization: str = "lemma",
    filter_del: bool = True
) -> CollatexWitness:
    """Converts a single manuscript text (plain or TEI XML) into a CollatexWitness."""
    is_xml = "<" in text and ">" in text

    if is_xml:
        logger.info(f"Processing witness '{siglum}' as TEI XML...")
        tei_parser = TEIParser()
        converter = EnrichedStrategyConverter(proc=processor, parser=tei_parser)
        tokens = converter.run(text, normalization=normalization, filter_del=filter_del)
    else:
        logger.info(f"Processing witness '{siglum}' as raw text...")
        converter = RawStrategyConverter(proc=processor)
        tokens = converter.run(text, normalization=normalization, filter_del=filter_del)

    return CollatexWitness(id=siglum, tokens=tokens)


async def run_pipeline(
    manuscripts: Dict[str, str],
    processor_type: str = "raw",
    language: str = "lati1261",
    normalization: str = "lemma",
    filter_del: bool = True,
    output_format: str = "application/json",
    algorithm: Optional[str] = None,
    collatex_url: Optional[str] = None,
    output_file: Optional[str] = None,
) -> Any:
    """Executes tokenization and collation for the provided manuscripts dictionary."""
    settings = Settings()
    collatex_base_url = collatex_url or settings.collatex_api_base_url or "http://localhost:7369"

    # 1. Initialize Processor
    processor = get_processor(processor_type, language)

    # 2. Tokenize all manuscripts
    witnesses: List[CollatexWitness] = []
    print("\n--- Tokenizing Manuscripts ---")
    for siglum, text in manuscripts.items():
        witness = tokenize_manuscript(
            siglum=siglum,
            text=text,
            processor=processor,
            normalization=normalization,
            filter_del=filter_del
        )
        witnesses.append(witness)
        print(f"  • Witness '{siglum}': {len(witness.tokens)} tokens generated")

    collatex_response = CollatexResponse(ref_id="custom_input", witnesses=witnesses)
    payload = collatex_response.model_dump(by_alias=True, exclude_none=True)

    # 3. Collate via CollateX Web Service
    print(f"\n--- Aligning via CollateX ({collatex_base_url}) ---")
    async with httpx.AsyncClient() as http_client:
        collatex_client = CollatexClient(base_url=collatex_base_url, http_client=http_client)
        try:
            result = await collatex_client.collate(
                payload=payload,
                output_format=output_format,
                algorithm=algorithm,
            )
            print("Alignment completed successfully!")
        except Exception as e:
            logger.warning(f"Could not connect to CollateX server at {collatex_base_url}: {e}")
            print("\n[NOTE] CollateX service unreachable. Displaying tokenization summary instead:")
            result = payload

    # 4. Display & Save Output
    print("\n--- Results Summary ---")
    if isinstance(result, dict) and "table" in result:
        print_alignment_table(result)
    elif isinstance(result, str):
        print(f"Raw Output ({output_format}):\n")
        print(result[:1000] + ("\n..." if len(result) > 1000 else ""))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))

    if output_file:
        save_path = Path(output_file)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as f:
            if isinstance(result, dict):
                json.dump(result, f, indent=2, ensure_ascii=False)
            else:
                f.write(result)
        print(f"\nResults saved to: {save_path.resolve()}")

    return result


def print_alignment_table(collatex_json: Dict[str, Any]):
    """Pretty prints a CollateX JSON alignment table in the terminal."""
    raw_witnesses = collatex_json.get("witnesses", [])
    witnesses = [
        w["id"] if isinstance(w, dict) and "id" in w else str(w)
        for w in raw_witnesses
    ]
    table = collatex_json.get("table", [])

    if not witnesses or not table:
        print("No alignment table data found.")
        return

    # Calculate column widths
    col_widths = []
    for col_idx, column in enumerate(table):
        max_len = 1
        for cell in column:
            if cell:
                token_item = cell[0]
                if isinstance(token_item, dict):
                    text_val = token_item.get("t", token_item.get("n", ""))
                else:
                    text_val = str(token_item)
                max_len = max(max_len, len(text_val.strip()))
        col_widths.append(max_len + 2)

    # Print header
    header = f"{'Witness':<12} | " + " | ".join(f"C{i+1:<{col_widths[i]-1}}" for i in range(len(table)))
    print("-" * len(header))
    print(header)
    print("-" * len(header))

    # Print rows for each witness
    for wit_idx, wit_id in enumerate(witnesses):
        row_cells = []
        for col_idx, column in enumerate(table):
            cell = column[wit_idx] if wit_idx < len(column) else []
            if cell:
                token_item = cell[0]
                if isinstance(token_item, dict):
                    t_val = token_item.get("t", token_item.get("n", "")).strip()
                else:
                    t_val = str(token_item).strip()
            else:
                t_val = "-"
            row_cells.append(f"{t_val:<{col_widths[col_idx]}}")
        print(f"{wit_id:<12} | " + " | ".join(row_cells))

    print("-" * len(header))



def main():
    parser = argparse.ArgumentParser(description="Run s-bridge pipeline on custom inline manuscript inputs.")
    parser.add_argument("--processor", choices=["raw", "classical", "modern"], default="raw",
                        help="NLP Processor type: 'raw' (fast split), 'classical' (CLTK/Stanza), 'modern' (Stanza).")
    parser.add_argument("--language", default="lati1261",
                        help="Language code (e.g. 'lati1261', 'anci1242').")
    parser.add_argument("--normalization", choices=["lemma", "text", "lemma+pos"], default="lemma",
                        help="Token normalization strategy.")
    parser.add_argument("--format", default="application/json",
                        choices=["application/json", "application/tei+xml", "image/svg+xml", "text/plain", "application/graphml+xml"],
                        help="Output format requested from CollateX.")
    parser.add_argument("--algorithm", choices=["dekker", "needleman-wunsch", "medite"], default=None,
                        help="CollateX alignment algorithm.")
    parser.add_argument("--collatex-url", default=None,
                        help="Custom CollateX API server URL.")
    parser.add_argument("--output-file", default="custom_collation_result.json",
                        help="Path to save collation output file.")

    args = parser.parse_args()

    asyncio.run(
        run_pipeline(
            manuscripts=MANUSCRIPTS,
            processor_type=args.processor,
            language=args.language,
            normalization=args.normalization,
            output_format=args.format,
            algorithm=args.algorithm,
            collatex_url=args.collatex_url,
            output_file=args.output_file,
        )
    )


if __name__ == "__main__":
    main()
