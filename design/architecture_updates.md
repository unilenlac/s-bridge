# Architecture Review and Updates

## Overview
This document outlines the recent architectural improvements to the σ-Bridge codebase, building upon the excellent structural refactoring initiated in the development branch. The goal was to refine the decoupling of HTTP clients, enforce secure data handling, and solidify the backend's agnostic nature.

## 1. Global HTTP Connection Pooling
The initiative to decouple `httpx.AsyncClient` from the individual wrapper classes (`DTSClient`, `CollatexClient`, `StemmarestClient`) was a strong architectural decision aimed at reusing HTTP connections and avoiding socket exhaustion.

**Enhancement:**
We have elevated this concept by implementing a true global connection pool. The `httpx.AsyncClient` is now instantiated once during the FastAPI `lifespan` event and stored in the application state (`app.state.http_client`). 
- **Why this matters:** FastAPI's `Depends` yields are scoped strictly to the HTTP request lifecycle. By moving the client instantiation to the application level, background tasks (like `run_collate_job`) can safely utilize the same connection pool without encountering `Event loop is closed` errors after the immediate API response is returned to the user.

## 2. Refined Preparator Pattern
The extraction of DTS-specific logic into `services/preparators.py` (`DtsPreparator`) successfully achieved Separation of Concerns by standardizing how source collections are pre-processed, regardless of the originating server.

**Enhancement:**
We updated the intermediate serialization format from `pickle` to `json`.
- **Why this matters:** While `pickle` is often associated with Python-native object storage, it inherently introduces a security vulnerability when handling data sourced from external, untrusted APIs. `json` provides the same memory footprint since both load the full dataset into memory concurrently, but it guarantees secure serialization and portability. 

## 3. Server-Agnostic Tracking
The TODO highlighting the redundancy of `dts_base_url` versus `collection_url` was spot on. If we are to support non-DTS sources in the future, tying our schema to "DTS" nomenclature is restrictive.

**Enhancement:**
We removed `dts_base_url` entirely from the `Job` and `Tradition` database schema. 
- **Why this matters:** Replacing it with a generic `collection_url` aligns perfectly with the agnostic goal. We retain `collection_id` as the human-readable slug (parsed from the resource) but rely on `collection_url` for routing and network requests.

## 4. Centralized Logging
As noted in `main.py`, the inline configuration of the `s-bridge` logger crowded the application entry point.

**Enhancement:**
We executed this TODO by abstracting the configuration into `core/logging.py`, keeping `main.py` clean while providing a scalable, structured logging foundation that can be extended with file handlers in the future.
