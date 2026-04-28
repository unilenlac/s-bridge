# Dynamic DTS Base URL Configuration

The `/dts/process-and-collate` endpoint requires a `collection_url` instead of a simple `collection_id`. This allows `s-bridge` to dynamically fetch collections from any compatible DTS server across different universities without relying on a hardcoded, global server address.

## JSON Payload Example
```json
{
  "collection_url": "http://ftsr-dev.unil.ch:8000/api/dts/v1/collection?id=s-bridge",
  "ref": "optional-specific-reference"
}
```

## URL Rules

When crafting the `collection_url`, the following structural rules must be met for the automatic extraction to work properly:

1. **Must include the base path and DTS specifier (`/api/dts/`)**: 
   The server splits the URL using `/api/dts/` to find the base server address.
   * ✅ `https://py-dts-demo.onrender.com/api/dts/v1/collection`
   * ❌ `https://py-dts-demo.onrender.com/collections` (will fail to parse)

2. **Must include the `id=` query parameter**:
   The server extracts the specific collection ID directly from the query string parameters.
   * ✅ `.../collection?id=1-1`
   * ✅ `.../collection?page=1&id=1-1`
   * ❌ `.../collection/1-1` (will fail as `id=` is missing)

## How it operates internally
If you provide `https://university-foo.edu/path/api/dts/v1/collection?id=xyz`, `s-bridge` will automatically deduce:
- **DTS Base Server:** `https://university-foo.edu/path`
- **Collection ID:** `xyz`

The server then sets up a distinct `DTSClient(base_url="https://university-foo.edu/path")` context securely tied to that job run. It also stores `dts_base_url` internally in the `Job` and `Tradition` database entries to remember where the resource was originally obtained from.
