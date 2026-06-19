import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, List

# Ensure project root is in the Python search path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import httpx
import stanza
from cltk import NLP

from core.config import Settings
from api.dependencies import ProcessingOptions
from services.tei_parser import TEIParser
from services.processors import ClassicalProcessor, ModernProcessor
from services.converters import EnrichedStrategyConverter, RawStrategyConverter
from services.preparators import DtsPreparator
from helpers.helpers import get_xml_from_dts_url
from clients.collatex_client import CollatexClient
from models.tokenization import CollatexResponse, CollatexWitness

# Setup simple console logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("benchmark")


def compute_alignment_metrics(collatex_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes various quality metrics from a Collatex alignment table response.
    """
    witnesses = collatex_json.get("witnesses", [])
    table = collatex_json.get("table", [])
    num_witnesses = len(witnesses)
    total_columns = len(table)

    consensus_columns = 0
    variant_columns = 0
    gap_columns = 0
    total_gaps = 0
    total_tokens = 0

    for column in table:
        tokens_in_col = []
        has_gap = False
        for cell in column:
            # cell is a list of token dicts (empty list represents a gap)
            if not cell:
                has_gap = True
                total_gaps += 1
            else:
                # cell[0] is the token representation
                norm_val = cell[0].get("n", "")
                if isinstance(norm_val, str):
                    norm_val = norm_val.strip()
                tokens_in_col.append(norm_val)
                total_tokens += len(cell)

        if has_gap:
            gap_columns += 1

        # Check if all witnesses have a token in this column
        if len(tokens_in_col) == num_witnesses:
            # If all values are identical, it is a consensus column
            if len(set(tokens_in_col)) == 1:
                consensus_columns += 1
            else:
                variant_columns += 1
        else:
            # Column has gaps. It is considered a variant column if there's disagreement
            # among the witnesses that do have a token.
            if len(tokens_in_col) >= 2 and len(set(tokens_in_col)) > 1:
                variant_columns += 1

    total_cells = total_columns * num_witnesses
    density = (total_cells - total_gaps) / total_cells if total_cells > 0 else 0
    density = round(density, 3)

    return {
        "total_columns": total_columns,
        "consensus_columns": consensus_columns,
        "variant_columns": variant_columns,
        "gap_columns": gap_columns,
        "total_gaps": total_gaps,
        "density": density,
        "total_tokens": total_tokens,
        "num_witnesses": num_witnesses,
    }


def mock_collate(witnesses: List[CollatexWitness]) -> Dict[str, Any]:
    """
    Simulates Collatex alignment table by performing a naive index-based alignment
    when the Collatex server is offline.
    """
    witness_ids = [w.id for w in witnesses]
    table = []

    max_len = max(len(w.tokens) for w in witnesses)
    for i in range(max_len):
        column = []
        for w in witnesses:
            if i < len(w.tokens):
                t = w.tokens[i]
                column.append([t.model_dump(by_alias=True, exclude_none=True)])
            else:
                column.append([])
        table.append(column)

    return {"witnesses": witness_ids, "table": table}


def load_local_witnesses(file_path: str) -> Dict[str, str]:
    """
    Loads witnesses and their XML content from a local milestone XML file.
    """
    import xml.etree.ElementTree as ET

    print(f"[Local] Loading witnesses from local XML file: {file_path}")

    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
    except Exception:
        # Wrap in root if not a single root document
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        root = ET.fromstring(f"<root>{content}</root>")

    xml_cache = {}
    witnesses = root.findall(".//witness")

    if not witnesses:
        # Fallback if no <witness> tags exist
        witness_id = Path(file_path).stem
        xml_cache[witness_id] = ET.tostring(root, encoding="utf-8").decode("utf-8")
    else:
        for w in witnesses:
            w_id = w.get("id")
            if not w_id:
                w_id = f"witness_{len(xml_cache) + 1}"
            xml_cache[w_id] = ET.tostring(w, encoding="utf-8").decode("utf-8")

    print(f"[Local] Loaded {len(xml_cache)} witnesses.")
    return xml_cache


async def fetch_witnesses_xml(
    collection_url: str, ref: str, settings: Settings, http_client: httpx.AsyncClient
) -> Dict[str, str]:
    """
    Resolves collection witness resource URLs for a given reference and downloads their raw XML.
    """
    print(f"\n[DTS] Querying collection resources for reference '{ref}'...")
    success, paths, title, resources = await DtsPreparator.run(
        url=collection_url,
        target_ref=ref,
        job_id=f"benchmark_{ref}",
        http_client=http_client,
        settings=settings,
    )
    if not success or not paths:
        raise ValueError(f"DTS preprocessing failed to find reference '{ref}'")

    prep_path = paths[0]
    with open(prep_path, "r", encoding="utf-8") as f:
        prep_data = json.load(f)

    # Clean up the temp pre_collation file generated by the preparator
    try:
        os.remove(prep_path)
    except OSError:
        pass

    xml_cache = {}
    witness_list = prep_data.get("witnesses", [])
    print(
        f"[DTS] Found {len(witness_list)} witnesses for reference '{ref}'. Downloading XML files..."
    )

    for witness in witness_list:
        witness_id = witness["id"]
        content_url = witness["content"]
        xml_data = await get_xml_from_dts_url(content_url, http_client, logger)
        xml_cache[witness_id] = xml_data

    print("[DTS] Successfully fetched and cached XML content.")
    return xml_cache


async def run_benchmark():
    parser = argparse.ArgumentParser(description="Benchmark s-bridge Alignment Quality")
    parser.add_argument(
        "--collection-url",
        default="http://ftsr-dev.unil.ch:8000/api/dts/v1/collection?id=sb-mp",
        help="DTS collection endpoint URL",
    )
    parser.add_argument(
        "--refs",
        default="107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,123,124,125,126,127,128,129,130,131,132,133,134,135,136,137,138,139,140,141,142,143,144,145,146,147,148",
        help="Comma-separated list of DTS references to benchmark",
    )
    parser.add_argument(
        "--local-file",
        default=None,
        help="Path to a local XML file containing multiple <witness> elements (bypasses DTS)",
    )
    parser.add_argument(
        "--output-dir",
        default="data/benchmarks",
        help="Directory to save collation JSON results",
    )

    args = parser.parse_args()

    # Load project settings
    settings = Settings()

    print("=" * 70)
    print("σ-BRIDGE ALIGNMENT BENCHMARK")
    print("=" * 70)
    if args.local_file:
        print(f"Source:         Local File ({args.local_file})")
        refs = ["local"]
    else:
        print(f"Collection URL: {args.collection_url}")
        refs = [r.strip() for r in args.refs.split(",") if r.strip()]
        print(f"References:     {', '.join(refs)}")
    print(f"Pipeline Type:  {settings.pipeline.value}")
    print(f"Language:       {settings.language.value}")
    print(f"CollateX URL:   {settings.collatex_api_base_url}")
    print("=" * 70)

    # 1. Initialize the processor once to avoid loading models repeatedly
    print("\nInitializing NLP models...")
    nlp_init_start = time.time()
    if settings.pipeline == "modern":
        proc = ModernProcessor(
            stanza.Pipeline(settings.language, processors="tokenize,pos,lemma")
        )
    else:
        proc = ClassicalProcessor(
            NLP(settings.language, backend="stanza", suppress_banner=True)
        )
    print(f"NLP models loaded in {time.time() - nlp_init_start:.2f}s.")

    # 2. Set up configurations to evaluate
    configs = [
        {
            "name": "Enriched (lemma+pos)",
            "strategy": "enriched",
            "normalization": "lemma+pos",
            "filter_del": True,
        },
        {
            "name": "Enriched (lemma)",
            "strategy": "enriched",
            "normalization": "lemma",
            "filter_del": True,
        },
        {
            "name": "Enriched (text)",
            "strategy": "enriched",
            "normalization": "text",
            "filter_del": True,
        },
        {
            "name": "Raw (text - body only)",
            "strategy": "raw",
            "normalization": "text",
            "filter_del": False,
        },
    ]

    all_results = {}

    async with httpx.AsyncClient(timeout=300.0) as http_client:
        collatex_client = CollatexClient(
            base_url=settings.collatex_api_base_url, http_client=http_client
        )

        for ref in refs:
            print(f"\n" + "#" * 60)
            print(f"### BENCHMARKING REFERENCE: {ref}")
            print("#" * 60)

            try:
                if args.local_file:
                    xml_cache = load_local_witnesses(args.local_file)
                else:
                    # Fetch XML files for this ref once
                    xml_cache = await fetch_witnesses_xml(
                        args.collection_url, ref, settings, http_client
                    )
            except Exception as e:
                print(f"❌ Error fetching resources for ref '{ref}': {e}")
                continue

            ref_results = []

            for config in configs:
                print(f"\nRunning strategy: {config['name']}...")
                start_time = time.time()

                # Setup the strategy's converter
                if config["strategy"] == "raw":
                    converter = RawStrategyConverter(proc=proc)
                else:
                    tag_dict = settings.load_tag_dictionary()
                    utils_dir = Path(__file__).parent.parent / "utils"
                    abbr_file = utils_dir / "abbr_classical_greek.csv"
                    parser = TEIParser(abbr_file=str(abbr_file), custom_tags=tag_dict)
                    converter = EnrichedStrategyConverter(proc=proc, parser=parser)

                # Process all cached XML contents to tokens
                collatex_witnesses = []
                tokenization_error = False

                for witness_id, xml_content in xml_cache.items():
                    try:
                        tokens = await asyncio.to_thread(
                            converter.run,
                            xml_content,
                            normalization=config["normalization"],
                            filter_del=config["filter_del"],
                        )
                        collatex_witnesses.append(
                            CollatexWitness(id=witness_id, tokens=tokens)
                        )
                    except Exception as e:
                        print(f"  ❌ Tokenization error for '{witness_id}': {e}")
                        tokenization_error = True
                        break

                if tokenization_error or not collatex_witnesses:
                    continue

                tokenization_time = time.time() - start_time

                # Collate via Collatex
                payload = CollatexResponse(
                    ref_id=ref, witnesses=collatex_witnesses
                ).model_dump(by_alias=True, exclude_none=True)

                collate_start = time.time()
                try:
                    collatex_result = await collatex_client.collate(
                        payload=payload, output_format="application/json"
                    )
                    is_mocked = False
                except Exception as e:
                    print(f"  ⚠️ Collatex alignment error: {e}")
                    print(
                        "  ⚠️ Using fallback offline mock aligner for benchmark results."
                    )
                    collatex_result = mock_collate(collatex_witnesses)
                    is_mocked = True

                collate_time = time.time() - collate_start
                total_time = time.time() - start_time

                # Compute quality metrics
                metrics = compute_alignment_metrics(collatex_result)
                metrics["tokenization_time"] = round(tokenization_time, 2)
                metrics["collate_time"] = round(collate_time, 2)
                metrics["total_time"] = round(total_time, 2)
                metrics["config_name"] = config["name"]
                metrics["is_mocked"] = is_mocked

                ref_results.append(metrics)

                # Save collation JSON result
                output_dir = Path(args.output_dir) / f"ref_{ref}"
                os.makedirs(output_dir, exist_ok=True)
                safe_name = (
                    config["name"]
                    .lower()
                    .replace(" ", "_")
                    .replace("(", "")
                    .replace(")", "")
                    .replace("-", "_")
                )
                filename = output_dir / f"collatex_{safe_name}.json"
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(collatex_result, f, indent=2, ensure_ascii=False)

                status_label = " (MOCKED)" if is_mocked else ""
                print(
                    f"  Done in {total_time:.2f}s (Tokens: {metrics['total_tokens']}, Columns: {metrics['total_columns']}, Consensus: {metrics['consensus_columns']}){status_label}"
                )

            all_results[ref] = ref_results

            # Print comparison table for this ref
            print(f"\nSummary table for Reference {ref}:")
            print(
                f"| {'Strategy/Parameter':<25} | {'Columns':<8} | {'Consensus':<9} | {'Variants':<8} | {'Gaps (Total)':<12} | {'Density':<8} | {'Time':<6} |"
            )
            print(
                f"|{'-' * 27}|{'-' * 10}|{'-' * 11}|{'-' * 10}|{'-' * 14}|{'-' * 10}|{'-' * 8}|"
            )
            for res in ref_results:
                mock_label = "*" if res.get("is_mocked") else ""
                print(
                    f"| {res['config_name'] + mock_label:<25} "
                    f"| {res['total_columns']:<8d} "
                    f"| {res['consensus_columns']:<9d} "
                    f"| {res['variant_columns']:<8d} "
                    f"| {res['total_gaps']:<12d} "
                    f"| {res['density'] * 100:<7.1f}% "
                    f"| {res['total_time']:<5.2f}s |"
                )
            print(
                "* indicates fallback mock aligner was used due to unreachable Collatex server."
            )

    # Group and sum stats by config name for aggregation
    agg_stats = {}
    if all_results:
        for ref, results in all_results.items():
            for res in results:
                cfg_name = res["config_name"]
                if cfg_name not in agg_stats:
                    agg_stats[cfg_name] = {
                        "total_columns": 0,
                        "consensus_columns": 0,
                        "variant_columns": 0,
                        "gap_columns": 0,
                        "total_gaps": 0,
                        "total_cells": 0,
                        "total_time": 0.0,
                        "is_mocked": False,
                    }

                agg_stats[cfg_name]["total_columns"] += res["total_columns"]
                agg_stats[cfg_name]["consensus_columns"] += res["consensus_columns"]
                agg_stats[cfg_name]["variant_columns"] += res["variant_columns"]
                agg_stats[cfg_name]["gap_columns"] += res["gap_columns"]
                agg_stats[cfg_name]["total_gaps"] += res["total_gaps"]
                # total cells for this run is columns * witnesses
                agg_stats[cfg_name]["total_cells"] += res["total_columns"] * res.get(
                    "num_witnesses", 4
                )
                agg_stats[cfg_name]["total_time"] += res["total_time"]
                if res.get("is_mocked", False):
                    agg_stats[cfg_name]["is_mocked"] = True

        for cfg in agg_stats:
            agg_stats[cfg]["total_time"] = round(agg_stats[cfg]["total_time"], 2)
            cells = agg_stats[cfg]["total_cells"]
            gaps = agg_stats[cfg]["total_gaps"]
            density = (cells - gaps) / cells if cells > 0 else 0
            agg_stats[cfg]["density"] = round(density, 3)

    # Format lookalike stdout text table
    stdout_table = ""
    if agg_stats:
        table_lines = []
        table_lines.append("=" * 70)
        table_lines.append("### OVERALL AGGREGATED BENCHMARK SUMMARY (ALL REFERENCES)")
        table_lines.append("=" * 70)
        table_lines.append(
            f"| {'Strategy/Parameter':<25} | {'Columns':<8} | {'Consensus':<9} | {'Variants':<8} | {'Gaps (Total)':<12} | {'Density':<8} | {'Time':<7} |"
        )
        table_lines.append(
            f"|{'-' * 27}|{'-' * 10}|{'-' * 11}|{'-' * 10}|{'-' * 14}|{'-' * 10}|{'-' * 9}|"
        )
        for cfg_name, stats in agg_stats.items():
            density = stats["density"]
            mock_label = "*" if stats["is_mocked"] else ""
            table_lines.append(
                f"| {cfg_name + mock_label:<25} "
                f"| {stats['total_columns']:<8d} "
                f"| {stats['consensus_columns']:<9d} "
                f"| {stats['variant_columns']:<8d} "
                f"| {stats['total_gaps']:<12d} "
                f"| {density * 100:<7.1f}% "
                f"| {stats['total_time']:<6.2f}s |"
            )
        table_lines.append("* indicates fallback mock aligner was used for at least one reference.")
        stdout_table = "\n".join(table_lines)

    # Assemble JSON structure containing ONLY aggregated data and text summary
    output_data = {}
    if agg_stats:
        output_data["aggregated"] = agg_stats
        output_data["text_summary"] = stdout_table

    # Save overall summary statistics to file
    summary_path = Path(args.output_dir) / "benchmark_summary.json"
    os.makedirs(Path(args.output_dir), exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"\n[BENCHMARK] Saved summary statistics to {summary_path}")

    # Also save markdown summary for direct preview as a table
    md_summary_path = Path(args.output_dir) / "benchmark_summary.md"
    if stdout_table:
        with open(md_summary_path, "w", encoding="utf-8") as f:
            f.write(stdout_table + "\n")
        print(f"[BENCHMARK] Saved markdown table to {md_summary_path}")

    # Print overall aggregated statistics
    if stdout_table:
        print(f"\n{stdout_table}")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
