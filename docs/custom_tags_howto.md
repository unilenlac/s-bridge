# Custom Tag Configuration — How-To Guide

The `TEIParser` supports dynamic editorial tag configuration. Instead of being limited to the built-in ENLAC tags (`unclear`, `add`, `del`, `abbr`, `seg`, `note`, `head`, `subst`, others), you can define your own tags and the metadata they should produce.

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
        "flags": {
            "unclear": true
        },
        "attributes": [
            "reason",
            "atLeast",
            "atMost"
        ]
    },
    "reproduction": {
        "flags": {
            "reproduction": true
        },
        "attributes": [
            "atLeast",
            "atMost"
        ]
    },
    "supplied": {
        "flags": {
            "supplied": true
        },
        "attributes": [
            "low",
            "medium",
            "high"
        ]
    },
    "handshift": {
        "flags": {
            "handshift": true
        },
        "attributes": [
            "hand"
        ]
    },
    "space": {
        "flags": {
            "space": true
        },
        "attributes": [
            "atLeast",
            "atMost"
        ]
    },
    "add": {
        "flags": {
            "add": true
        },
        "attributes": [
            "hand",
            "place",
            "type",
            "rend"
        ]
    },
    "del": {
        "flags": {
            "del": true
        },
        "attributes": [
            "rend",
            "hand",
            "atLeast",
            "atMost"
        ]
    },
    "abbr": {
        "flags": {
            "abbr": true
        },
        "attributes": [
            "type"
        ]
    },
    "seg": {
        "flags": {
            "seg": true
        },
        "attributes": [
            "type",
            "hand",
            "place",
            "part"
        ]
    },
    "note": {
        "flags": {
            "note": true
        },
        "attributes": [
            "type"
        ]
    },
    "head": {
        "flags": {
            "head": true
        },
        "attributes": [
            "type",
            "place"
        ]
    },
    "subst": {
        "flags": {
            "subst": true
        },
        "attributes": [
            "type"
        ]
    },
    "gap": {
        "flags": {
            "gap": true
        }
    },
    "choice": {
        "flags": {
            "choice": true
        },
        "attributes": [
            "place",
            "hand",
            "notation"
        ]
    },
    "c": {
        "flags": {
            "c": true
        },
        "attributes": [
            "type"
        ]
    },
    "hi": {
        "flags": {
            "hi": true
        }
    },
    "name": {
        "flags": {
            "name": true
        }
    },
    "num": {
        "flags": {
            "num": true
        },
        "attributes": [
            "value",
            "type"
        ]
    },
    "quote": {
        "flags": {
            "quote": true
        }
    },
    "sic": {
        "flags": {
            "sic": true
        }
    }
}
```

---

## Self-Closing Tags

Self-closing tags like `<unclear/>` or `<damage/>` are fully supported. The parser automatically applies their metadata to the neighboring word boundary:

- If followed by text without a space: metadata attaches to the **next** word.
- If followed by a space: metadata attaches to the **previous** word.

No special configuration is needed — this works for any tag in your config.

When omitted, the ENLAC defaults are used.
