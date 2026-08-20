import argparse
import asyncio
import csv
import io
import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Dict, Any, List

# Ensure project root is in the Python search path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import httpx
import stanza
import networkx as nx
from cltk import NLP

from core.config import Settings
from services.tei_parser import TEIParser
from services.processors import ClassicalProcessor, ModernProcessor, RawProcessor
from services.converters import EnrichedStrategyConverter, RawStrategyConverter
from services.preparators import DtsPreparator
from helpers.helpers import get_xml_from_dts_url
from clients.collatex_client import CollatexClient
from models.tokenization import CollatexResponse, CollatexWitness

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("graph_analyzer")


async def fetch_witnesses_xml_from_entries(
    witness_list: List[Dict[str, Any]], ref: str, http_client: httpx.AsyncClient
) -> Dict[str, str]:
    """
    Downloads XML content for each witness in the prepared witness list for a given reference.
    """
    print(
        f"[DTS] Found {len(witness_list)} witnesses for reference '{ref}'. Downloading XML..."
    )
    xml_cache = {}
    for witness in witness_list:
        witness_id = witness["id"]
        content_url = witness["content"]
        xml_data = await get_xml_from_dts_url(content_url, http_client, logger)
        xml_cache[witness_id] = xml_data

    print(f"[DTS] Successfully downloaded {len(xml_cache)} XML files for ref '{ref}'.")
    return xml_cache


async def main():
    parser = argparse.ArgumentParser(
        description="Analyze Variant Graphs from CollateX using NetworkX across NLP strategies and CollateX algorithms"
    )
    parser.add_argument(
        "--collection-url",
        default="http://ftsr-dev.unil.ch:8000/api/dts/v1/collection?id=sb-mp",
        help="DTS collection endpoint URL",
    )
    parser.add_argument(
        "--refs",
        default="107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,123,124,125,126,127,128,129,130,131,132,133,134,135,136,137,138,139,140,141,143,144,145,146,147,148",
        help="Comma-separated list of DTS references to analyze",
    )
    parser.add_argument(
        "--collatex-url",
        default=None,
        help="Override CollateX server URL",
    )
    parser.add_argument(
        "--algorithms",
        default="dekker,needleman-wunsch,medite",
        help="Comma-separated CollateX alignment algorithms to evaluate (e.g. dekker, needleman-wunsch, medite)",
    )
    parser.add_argument(
        "--algorithm",
        default=None,
        help="Single algorithm override for backward compatibility",
    )
    parser.add_argument(
        "--skip-dekker-refs",
        default="142",
        help="Comma-separated list of references to skip 'dekker' algorithm on (default: 142)",
    )

    args = parser.parse_args()
    settings = Settings()

    collatex_base_url = args.collatex_url or settings.collatex_api_base_url
    refs = [r.strip() for r in args.refs.split(",") if r.strip()]
    skip_dekker_refs = [
        r.strip() for r in args.skip_dekker_refs.split(",") if r.strip()
    ]

    # Parse and normalize requested algorithms
    raw_algos = args.algorithm or args.algorithms
    algorithms: List[str] = []
    for a in raw_algos.split(","):
        a_clean = a.strip().lower().replace("_", "-")
        if a_clean in ["dekker", "needleman-wunsch", "medite"]:
            if a_clean not in algorithms:
                algorithms.append(a_clean)
        elif a_clean:
            print(
                f"⚠️ Warning: Unrecognized algorithm '{a.strip()}'. Supported: dekker, needleman-wunsch, medite"
            )

    if not algorithms:
        algorithms = ["dekker", "needleman-wunsch", "medite"]

    print("=" * 80)
    print("σ-BRIDGE VARIANT GRAPH ANALYSIS (NETWORKX)")
    print("=" * 80)
    print(f"Collection URL: {args.collection_url}")
    print(f"References:     {', '.join(refs)}")
    print(f"Pipeline Type:  {settings.pipeline.value}")
    print(f"Language:       {settings.language.value}")
    print(f"CollateX URL:   {collatex_base_url}")
    print(f"Algorithms:     {', '.join(algorithms)}")
    print("=" * 80)

    # Initialize NLP models
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

    # Configurations to evaluate
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
            "name": "Raw (text)",
            "strategy": "raw",
            "normalization": "text",
            "filter_del": False,
        },
    ]

    aggregated_results: Dict[tuple, Dict[str, Any]] = {}
    all_reference_results: List[Dict[str, Any]] = []

    # Configure HTTP client with connection limits and timeouts
    transport = httpx.AsyncHTTPTransport(retries=3)
    timeout_cfg = httpx.Timeout(60.0, connect=15.0)

    async with httpx.AsyncClient(
        transport=transport, timeout=timeout_cfg
    ) as http_client:
        collatex_client = CollatexClient(
            base_url=collatex_base_url, http_client=http_client
        )

        # 1. Pre-process the entire DTS collection ONCE for all sections
        print("\n[DTS] Preprocessing collection manifest once for all references...")
        manifest_job_id = f"benchmark_manifest_{int(time.time())}"
        success, paths, collection_title, resources = await DtsPreparator.run(
            url=args.collection_url,
            target_ref=None,
            job_id=manifest_job_id,
            http_client=http_client,
            settings=settings,
        )

        if not success or not paths:
            raise ValueError(
                f"DTS preprocessing failed for collection '{args.collection_url}'"
            )

        # Load section manifests into memory: ref -> witness entries list
        sections_by_ref: Dict[str, List[Dict[str, Any]]] = {}
        for p in paths:
            try:
                with open(p, "r", encoding="utf-8") as f:
                    sec_data = json.load(f)
                    ref_id = str(sec_data.get("ref_id", ""))
                    if ref_id:
                        sections_by_ref[ref_id] = sec_data.get("witnesses", [])
            except Exception as e:
                logger.warning(f"Error reading section manifest {p}: {e}")

        print(f"[DTS] Manifest loaded with {len(sections_by_ref)} available sections.")

        # Clean up temporary manifest directory on disk
        if paths:
            temp_manifest_dir = os.path.dirname(paths[0])
            try:
                if os.path.exists(temp_manifest_dir):
                    shutil.rmtree(temp_manifest_dir)
            except OSError:
                pass

        for ref in refs:
            print("\n" + "#" * 60)
            print(f"### ANALYZING REFERENCE: {ref}")
            print("#" * 60)

            witness_entries = sections_by_ref.get(ref)
            if not witness_entries:
                print(
                    f"❌ Reference '{ref}' not found in DTS collection manifest. Skipping."
                )
                continue

            try:
                xml_cache = await fetch_witnesses_xml_from_entries(
                    witness_entries, ref, http_client
                )
            except Exception as e:
                print(f"❌ Error fetching XML for ref '{ref}': {e}")
                continue

            ref_results: List[Dict[str, Any]] = []

            for config in configs:
                print(f"\nTokenizing strategy: {config['name']}...")
                tok_start = time.time()

                # Setup the strategy's converter
                if config["strategy"] == "raw":
                    converter = RawStrategyConverter(proc=RawProcessor())
                else:
                    tag_dict = settings.load_tag_dictionary()
                    utils_dir = Path(__file__).parent.parent / "utils"
                    abbr_file = utils_dir / "abbr_classical_greek.csv"
                    parser = TEIParser(abbr_file=str(abbr_file), custom_tags=tag_dict)
                    converter = EnrichedStrategyConverter(proc=proc, parser=parser)

                collatex_witnesses: List[CollatexWitness] = []
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

                tok_time = time.time() - tok_start
                total_tokens = sum(len(w.tokens) for w in collatex_witnesses)
                print(
                    f"  ✓ Tokenized {len(collatex_witnesses)} witnesses ({total_tokens} tokens) in {tok_time:.2f}s."
                )

                # Prepare CollateX JSON payload (done once per NLP configuration)
                payload = CollatexResponse(
                    ref_id=ref, witnesses=collatex_witnesses
                ).model_dump(by_alias=True, exclude_none=True)

                # Determine algorithms to run for this reference
                ref_algos = [
                    a
                    for a in algorithms
                    if not (a == "dekker" and ref in skip_dekker_refs)
                ]

                if "dekker" in algorithms and ref in skip_dekker_refs:
                    print(
                        f"  ℹ️ Skipping 'dekker' for reference '{ref}' (exceeds complexity budget)."
                    )

                # Now evaluate each requested CollateX algorithm on the tokenized payload
                for algo in ref_algos:
                    print(f"  Running CollateX algorithm: {algo}...")
                    algo_start = time.time()

                    try:
                        graphml_data = await collatex_client.collate(
                            payload=payload,
                            output_format="application/graphml+xml",
                            algorithm=algo,
                        )
                    except Exception as e:
                        print(f"    ❌ Collatex alignment error ({algo}): {e}")
                        continue

                    # Parse GraphML with NetworkX
                    try:
                        G = nx.read_graphml(io.BytesIO(graphml_data.encode("utf-8")))
                    except Exception as e:
                        print(f"    ❌ NetworkX GraphML parsing error ({algo}): {e}")
                        continue

                    # Compute structural metrics
                    num_nodes = G.number_of_nodes()
                    num_edges = G.number_of_edges()

                    # Merge Ratio: higher means more witness tokens merged into the same graph node
                    merge_ratio = total_tokens / num_nodes if num_nodes > 0 else 0

                    # Variation Points: nodes where paths split (out_degree > 1)
                    variation_points = 0
                    for node in G.nodes():
                        if G.out_degree(node) > 1:
                            variation_points += 1

                    collate_time = time.time() - algo_start
                    total_time = tok_time + collate_time

                    res_dict = {
                        "reference": ref,
                        "config_name": config["name"],
                        "strategy": config["strategy"],
                        "normalization": config["normalization"],
                        "algorithm": algo,
                        "total_tokens": total_tokens,
                        "nodes": num_nodes,
                        "edges": num_edges,
                        "merge_ratio": round(merge_ratio, 3),
                        "variation_points": variation_points,
                        "tok_time": round(tok_time, 2),
                        "collate_time": round(collate_time, 2),
                        "time": round(total_time, 2),
                    }
                    ref_results.append(res_dict)
                    all_reference_results.append(res_dict)

                    # Accumulate for overall aggregated statistics
                    agg_key = (config["name"], algo)
                    if agg_key not in aggregated_results:
                        aggregated_results[agg_key] = {
                            "config_name": config["name"],
                            "algorithm": algo,
                            "total_tokens": 0,
                            "nodes": 0,
                            "edges": 0,
                            "variation_points": 0,
                            "count": 0,
                            "tok_time": 0.0,
                            "collate_time": 0.0,
                            "total_time": 0.0,
                        }
                    aggregated_results[agg_key]["total_tokens"] += total_tokens
                    aggregated_results[agg_key]["nodes"] += num_nodes
                    aggregated_results[agg_key]["edges"] += num_edges
                    aggregated_results[agg_key]["variation_points"] += variation_points
                    aggregated_results[agg_key]["count"] += 1
                    aggregated_results[agg_key]["tok_time"] += tok_time
                    aggregated_results[agg_key]["collate_time"] += collate_time
                    aggregated_results[agg_key]["total_time"] += total_time

            # Print comparison table for this reference
            if ref_results:
                print(f"\nVariant Graph Analysis Summary for Reference {ref}:")
                print(
                    f"| {'Strategy/Parameter':<25} | {'Algorithm':<17} | {'Tokens':<8} | {'Nodes (V)':<10} | {'Edges (E)':<10} | {'Merge Ratio':<12} | {'Var Points':<11} | {'Tok Time':<10} | {'Collate':<9} | {'Total Time':<11} |"
                )
                print(
                    f"|{'-' * 27}|{'-' * 19}|{'-' * 10}|{'-' * 12}|{'-' * 12}|{'-' * 14}|{'-' * 13}|{'-' * 12}|{'-' * 11}|{'-' * 13}|"
                )
                for res in ref_results:
                    print(
                        f"| {res['config_name']:<25} "
                        f"| {res['algorithm']:<17} "
                        f"| {res['total_tokens']:<8d} "
                        f"| {res['nodes']:<10d} "
                        f"| {res['edges']:<10d} "
                        f"| {res['merge_ratio']:<12.3f} "
                        f"| {res['variation_points']:<11d} "
                        f"| {res['tok_time']:<8.2f}s  "
                        f"| {res['collate_time']:<7.2f}s  "
                        f"| {res['time']:<9.2f}s  |"
                    )
                print("-" * 130)

        # Generate overall aggregated summary tables if multiple references or multiple results
        if aggregated_results:
            summary_lines = []
            summary_lines.append("# Overall Aggregated Variant Graph Summary")
            summary_lines.append("")
            summary_lines.append(
                "======================================================================================================================================"
            )
            summary_lines.append(
                "### OVERALL AGGREGATED VARIANT GRAPH SUMMARY (ALL REFERENCES & ALGORITHMS)"
            )
            summary_lines.append(
                "======================================================================================================================================"
            )
            summary_lines.append(
                f"| {'Strategy/Parameter':<25} | {'Algorithm':<17} | {'Tokens':<8} | {'Nodes (V)':<10} | {'Edges (E)':<10} | {'Merge Ratio':<12} | {'Var Points':<11} | {'Tok Time':<10} | {'Collate':<9} | {'Total Time':<11} |"
            )
            summary_lines.append(
                f"|{'-' * 27}|{'-' * 19}|{'-' * 10}|{'-' * 12}|{'-' * 12}|{'-' * 14}|{'-' * 13}|{'-' * 12}|{'-' * 11}|{'-' * 13}|"
            )
            for (cfg_name, algo), stats in aggregated_results.items():
                tot_tokens = stats["total_tokens"]
                tot_nodes = stats["nodes"]
                merge_ratio = tot_tokens / tot_nodes if tot_nodes > 0 else 0
                tok_t = stats["tok_time"]
                collate_t = stats["collate_time"]
                tot_t = stats["total_time"]
                summary_lines.append(
                    f"| {cfg_name:<25} "
                    f"| {algo:<17} "
                    f"| {tot_tokens:<8d} "
                    f"| {tot_nodes:<10d} "
                    f"| {stats['edges']:<10d} "
                    f"| {merge_ratio:<12.3f} "
                    f"| {stats['variation_points']:<11d} "
                    f"| {tok_t:<8.2f}s  "
                    f"| {collate_t:<7.2f}s  "
                    f"| {tot_t:<9.2f}s  |"
                )

            summary_lines.append("")
            summary_lines.append("## Per-Algorithm Breakdown")

            # Also generate individual algorithm summary tables
            for algo in algorithms:
                algo_stats = [
                    (cfg_name, stats)
                    for (cfg_name, a), stats in aggregated_results.items()
                    if a == algo
                ]
                if not algo_stats:
                    continue

                summary_lines.append("")
                summary_lines.append(
                    f"### Aggregated Summary: Algorithm '{algo.upper()}'"
                )
                summary_lines.append(
                    f"| {'Strategy/Parameter':<25} | {'Tokens':<8} | {'Nodes (V)':<10} | {'Edges (E)':<10} | {'Merge Ratio':<12} | {'Var Points':<11} | {'Tok Time':<10} | {'Collate':<9} | {'Total Time':<11} |"
                )
                summary_lines.append(
                    f"|{'-' * 27}|{'-' * 10}|{'-' * 12}|{'-' * 12}|{'-' * 14}|{'-' * 13}|{'-' * 12}|{'-' * 11}|{'-' * 13}|"
                )
                for cfg_name, stats in algo_stats:
                    tot_tokens = stats["total_tokens"]
                    tot_nodes = stats["nodes"]
                    merge_ratio = tot_tokens / tot_nodes if tot_nodes > 0 else 0
                    tok_t = stats["tok_time"]
                    collate_t = stats["collate_time"]
                    tot_t = stats["total_time"]
                    summary_lines.append(
                        f"| {cfg_name:<25} "
                        f"| {tot_tokens:<8d} "
                        f"| {tot_nodes:<10d} "
                        f"| {stats['edges']:<10d} "
                        f"| {merge_ratio:<12.3f} "
                        f"| {stats['variation_points']:<11d} "
                        f"| {tok_t:<8.2f}s  "
                        f"| {collate_t:<7.2f}s  "
                        f"| {tot_t:<9.2f}s  |"
                    )

            # Print to stdout
            print("\n" + "\n".join(summary_lines[2:]))
            print("=" * 130)

            # Save to docs/variant_graph_summary.md
            docs_dir = Path(__file__).parent.parent / "docs"
            os.makedirs(docs_dir, exist_ok=True)
            output_file = docs_dir / "variant_graph_summary.md"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("\n".join(summary_lines) + "\n")
            print(f"\n[INFO] Saved overall aggregated summary to {output_file}")

        # Save all reference-level results to CSV if any were generated
        if all_reference_results:
            docs_dir = Path(__file__).parent.parent / "docs"
            os.makedirs(docs_dir, exist_ok=True)
            csv_output_file = docs_dir / "variant_graph_reference_metrics.csv"
            try:
                with open(csv_output_file, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(
                        f,
                        fieldnames=[
                            "reference",
                            "config_name",
                            "strategy",
                            "normalization",
                            "algorithm",
                            "total_tokens",
                            "nodes",
                            "edges",
                            "merge_ratio",
                            "variation_points",
                            "tok_time",
                            "collate_time",
                            "time",
                        ],
                    )
                    writer.writeheader()
                    writer.writerows(all_reference_results)
                print(f"\n[INFO] Saved reference-level metrics to {csv_output_file}")
            except Exception as e:
                print(f"\n❌ Error writing CSV file: {e}")


if __name__ == "__main__":
    asyncio.run(main())
