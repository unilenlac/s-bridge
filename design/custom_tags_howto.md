# Custom Tag Configuration — How-To Guide

The `TEIParser` supports dynamic editorial tag configuration. Instead of being limited to the built-in ENLAC tags (`unclear`, `add`, `del`, `abbr`, `seg`, `note`, `head`, `subst`, others), you can define your own tags and the metadata they should produce.

## Quick Start

Pass a `custom_tags` dictionary when creating a `TEIParser`:

```python
from services.tei_parser import TEIParser

custom_tags = {
    "damage": {
        "flags": {"damage": True},
        "attributes": ["extent"],
    }
}

parser = TEIParser(custom_tags=custom_tags)
clean_text, metadata_map = parser.parse('<root>Some <damage extent="2 chars"/>broken text.</root>')
# metadata for "broken" → {"damage": True, "damage_extent": "2 chars"}
```

> [!NOTE]
> When `custom_tags` is omitted (or `None`), the parser falls back to the default ENLAC tag set automatically.

---

## Config Format

Each key in the dictionary is an XML tag name. Its value is a config object with these optional fields:

### `flags` — Static metadata

Key-value pairs always added to the metadata when this tag is encountered.

```json
{"flags": {"unclear": true}}
```

Result: every word inside `<unclear>` gets `{"unclear": true}` in its metadata.

### `attributes` — Single-value XML attributes

List of XML attribute names to extract. The metadata key becomes `{tag}_{attr}`.

```json
{"attributes": ["reason"]}
```

`<unclear reason="illegible">` → `{"unclear_reason": "illegible"}`

### `attributes_list` — Space-separated XML attributes

Like `attributes`, but splits the value on spaces into a Python list.

```json
{"attributes_list": ["place"]}
```

`<add place="margin right">` → `{"add_place": ["margin", "right"]}`

### `attribute_map` — Custom key names

Maps an XML attribute name to a custom metadata key (when the default `{tag}_{attr}` naming isn't desired).

```json
{"attribute_map": {"rend": "del_reason"}}
```

`<del rend="strike">` → `{"del_reason": "strike"}` (not `del_rend`)

### `defaults` — Fallback values

Default values for metadata keys when the corresponding XML attribute is absent.

```json
{"defaults": {"del_reason": "other"}}
```

`<del>` (no `rend`) → `{"del_reason": "other"}`

---

## Full Example: ENLAC Default Config

This is what the parser uses when no `custom_tags` are provided:

```python
{
    "unclear": {
        "flags": {"unclear": True},
        "attributes": ["reason"],
    },
    "add": {
        "flags": {"add": True},
        "attributes": ["hand"],
    },
    "del": {
        "flags": {"del": True},
        "attribute_map": {"rend": "del_reason"},
        "defaults": {"del_reason": "other"},
    },
    "abbr": {
        "flags": {"abbr": True},
        "attributes": ["type"],
    },
    "seg": {
        "attributes": ["type", "part"],
    },
    "note": {
        "flags": {"note": True},
        "attributes": ["type"],
    },
    "head": {
        "flags": {"head": True},
    },
    "subst": {
        "flags": {"subst": True},
    },
}
```

---

## Self-Closing Tags

Self-closing tags like `<unclear/>` or `<damage/>` are fully supported. The parser automatically applies their metadata to the neighboring word boundary:

- If followed by text without a space: metadata attaches to the **next** word.
- If followed by a space: metadata attaches to the **previous** word.

No special configuration is needed — this works for any tag in your config.

---

## Via the API

The `/convert` endpoint accepts an optional `custom_tags` JSON body parameter (Note: using GET with a body is unconventional but supported by some clients, or you may prefer to stick to standard GET params if not using custom tags).

```bash
curl -X GET "http://localhost:8000/convert?text=..." \
  -H "Content-Type: application/json" \
  -d '{"custom_tags": {"myTag": {"flags": {"custom": true}}}}'
```

When omitted, the ENLAC defaults are used.
