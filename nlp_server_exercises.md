# NLP Server Exercises

*Write your answers directly below each question.*

## Section 1: Architecture & API Layer
**Focus**: FastAPI routing, dependencies, and configuration.

1. **Dependency Injection**: In `api/dependencies.py`, how is the `Converter` instance provided to the `/convert` endpoint? Explain the difference in initialization between the `RawStrategyConverter` and the `EnrichedStrategyConverter`. 

**Answer:**
> 

2. **Lifespan Management**: Looking at `main.py`, the `Processor` (either `ModernProcessor` or `ClassicalProcessor`) is initialized in the `lifespan` context manager. Why is this preferable to initializing the processor inside the endpoint function or directly at the module level?

**Answer:**
> 

3. **Format Support**: The `converter_dep` dependency handles `tei`, `json`, and `text` formats. Currently, `json` and `text` raise a `NotImplementedError`. What changes would you need to make in `converters.py` and `dependencies.py` to seamlessly support plain text input while still using the generic `Processor`?

**Answer:**
> 

## Section 2: Data Models & Serialization
**Focus**: Pydantic models and field aliases.

1. **Token Serialization**: In `models/collatex.py`, the `Token` model uses `serialization_alias` for many fields (e.g., `text` becomes `t`, `normalization` becomes `n`). Why might this be useful for the response of the `/convert` endpoint?

**Answer:**
> 

2. **Excluding Fields**: The `char_start` and `char_stop` fields are defined with `exclude=True`. Why are these character offsets needed during processing but explicitly excluded from the final JSON payload sent to the client?

**Answer:**
> 

3. **Pydantic dumps**: In `converters.py`, `token.model_dump(by_alias=False, exclude_none=True)` is called. Why must `by_alias` be `False` when reconstructing the token after merging it with editorial metadata?

**Answer:**
> 

## Section 3: NLP Processors
**Focus**: Linguistic processing, tokenization, and punctuation handling.

1. **Punctuation Merging**: Both `ClassicalProcessor` and `ModernProcessor` contain custom logic to handle tokens where `pos_tag == "PUNCT"`. Describe exactly what this logic does to the preceding token. What happens to the punctuation character itself?

**Answer:**
> 

2. **Normalization Strategies**: The `process` method accepts a `normalization` argument (e.g., `lemma`, `text`, `original`, `lemma+pos`). Trace how `lemma+pos` is constructed from a Stanza or CLTK word object. What happens if the `lemma` is missing from the underlying NLP library's output?

**Answer:**
> 

## Section 4: Converters & Metadata Merging
**Focus**: The "Enriched" orchestration phase.

1. **The Three-Step Dance**: In `EnrichedStrategyConverter.run()`, the data is processed in three distinct steps. Summarize the input and output of each step:
   - Step 1: `self.parser.parse(data)`
   - Step 2: `self.processor.process(clean_text, ...)`
   - Step 3: The `for token in raw_tokens:` loop.

**Answer:**
> 

2. **Offset Calculation**: In the token merging loop inside `converters.py` (lines 30-38), there is logic to calculate `char_start` and `char_stop` if the token doesn't already have them. Why might a token not have these offsets from the NLP processor, and why is `current_char_offset += len(token.original) + 1` used as the fallback?

**Answer:**
> 

3. **The Filtering Bug (Practical Exercise)**: In `converters.py`, there is a comment: `# THE FILTERING LOGIC and it is wrong for following tokens.`.
   ```python
   if filter_del and editorial_metadata.get("del") is True:
       continue # Skip this token entirely
   ```
   **Task**: Analyze why simply `continue`-ing the loop here might cause issues for the *subsequent* tokens in the string (hint: consider what `continue` does to `current_char_offset` logic if it is placed *after* the offset calculation, vs what happens to the character offsets of subsequent tokens if a token is removed). Propose a fix for this bug.

**Answer:**
> 

## Section 5: TEI Parsing (ElementTree)
**Focus**: XML parsing paradigms using `xml.etree.ElementTree`.

1. **Text vs Tail**: The `TEIParser` heavily relies on the distinction between an element's `.text` and its `.tail`. Explain the difference between these two properties in the context of `ElementTree`. Provide a short XML snippet that clearly demonstrates both.

**Answer:**
> 

2. **In-place Modification**: The `_resolve_hyphenation_and_breaks` function modifies the `ElementTree` in place before text extraction begins. Why is it conceptually cleaner to mutate the XML tree to resolve hyphens (e.g., joining `<w>` tags across `<lb/>` or `<pb/>` tags) *before* doing any metadata accumulation or text extraction?

**Answer:**
> 
