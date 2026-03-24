import asyncio
import time
import logging

from main import app
from core.config import Settings
from clients.dts_client import DTSClient
from services.tei_parser import TEIParser
from services.processors import ClassicalProcessor
from services.converters import EnrichedStrategyConverter
from services.witness_service import WitnessService
from api.dependencies import ProcessingOptions
from models.tokenization import CollatexWitness, CollatexResponse

# Silence verbose loggers to make console output readable
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("services").setLevel(logging.WARNING)
logging.getLogger("clients").setLevel(logging.WARNING)

class OldWitnessService:
    """The original sequential implementation we just replaced."""
    def __init__(self, fetcher):
        self.fetcher = fetcher

    async def process_witnesses(self, resources, converter, options, ref=None):
        witnesses = []
        for resource in resources:
            try:
                xml_data = await self.fetcher.get_document(resource, ref=ref)
                tokens = converter.run(
                    xml_data,
                    normalization=options.normalization,
                    filter_del=options.filter_del
                )
                witnesses.append(CollatexWitness(id=resource, tokens=tokens))
            except Exception as e:
                raise ValueError(f"Failed to process {resource}: {e}")
        return CollatexResponse(witnesses=witnesses)

async def run_benchmark():
    # 1. Dependency Injection setup
    fetcher = DTSClient(base_url=Settings().dts_api_base_url)
    processor = app.state.proc  # Already a ClassicalProcessor instance
    parser = TEIParser()
    converter = EnrichedStrategyConverter(proc=processor, parser=parser)
    options = ProcessingOptions(normalization="NFD", filter_del=True)
    
    # 2. Pick witnesses that we know contain ref="109"
    resources = ['athous-iviron-450', 'brescia-A-III-3-72', 'ebe-1027']
    
    print(f"\n==============================================")
    print(f"Benchmarking {len(resources)} XML Witnesses via DTS")
    print(f"==============================================\n")
    
    # 3. Simulate Old Architecture
    old_service = OldWitnessService(fetcher)
    t0 = time.time()
    await old_service.process_witnesses(resources, converter, options, ref="109")
    t1 = time.time()
    old_time = t1 - t0
    print(f" Old Sequential Architecture : {old_time:.3f} seconds")
    
    # 4. Simulate New Architecture
    new_service = WitnessService(fetcher)
    t0 = time.time()
    await new_service.process_witnesses(resources, converter, options, ref="109")
    t1 = time.time()
    new_time = t1 - t0
    print(f" New Parallel Architecture   : {new_time:.3f} seconds\n")
    
    # 5. Conclusion
    speedup = old_time / new_time if new_time > 0 else 0
    print(f"Performance Gain: The asyncio refactor was {speedup:.2f}x faster!")

if __name__ == "__main__":
    from fastapi.testclient import TestClient
    
    # Wrap in TestClient to execute the FastAPI lifespan events (which load Stanza into memory)
    with TestClient(app):
        # By the time this block runs, Stanza is warm and bound to app.state.proc
        asyncio.run(run_benchmark())
