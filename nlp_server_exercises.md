# NLP Server Exercises

*Write your answers directly below each question.*

## Section 1: Architecture & API Layer
**Focus**: FastAPI routing, dependencies, and configuration.

1. **Dependency Injection**: In `api/dependencies.py`, how is the `Converter` instance provided to the `/convert` endpoint? Explain the difference in initialization between the `RawStrategyConverter` and the `EnrichedStrategyConverter`. 

**Answer:**
> 
The converter instance is provided through a selection made in dependencies. The converter_dep function helps selecting the correct converter based on format and strategies given through the endpoint as parameters in the http post request. fastAPI includes Query which facilitates this.

The main difference between Raw and enriched is the fact that Enriched uses a parser. In the enriched, a parser is initialized with specific abbreviation file and tag dictionary. It will be used  to parse the text before handling it to cltk to analyze.

2. **Lifespan Management**: Looking at `main.py`, the `Processor` (either `ModernProcessor` or `ClassicalProcessor`) is initialized in the `lifespan` context manager. Why is this preferable to initializing the processor inside the endpoint function or directly at the module level?

**Answer:**
> 
 It is initialized in the lifespan context manager given through fastAPI instead of directly at the module level because everything contained in lifespan is ran ONCE at server launch. then the processor is set as an app.state variable, accessible through fastAPI Request


3. **Format Support**: The `converter_dep` dependency handles `tei`, `json`, and `text` formats. Currently, `json` and `text` raise a `NotImplementedError`. What changes would you need to make in `converters.py` and `dependencies.py` to seamlessly support plain text input while still using the generic `Processor`?

**Answer:**
> 
in converters.py, no change would be needed, that's the beauty of decoupling it in such a way. in dependencies.py, we would need to give a specific parser for text and json. Presumably JSONParser and  TEXTParser/PLAINParser. We would need to implement those however.

## Section 2: Data Models & Serialization
**Focus**: Pydantic models and field aliases.

1. **Token Serialization**: In `models/collatex.py`, the `Token` model uses `serialization_alias` for many fields (e.g., `text` becomes `t`, `normalization` becomes `n`). Why might this be useful for the response of the `/convert` endpoint?

**Answer:**
> 
As is, the Token(BaseModel) is largely for documentation as the model_config = ConfigDict(Extra="allow") actually allows for more entries than those stated as Optionnal. Now, onto the serialization question, I suppose it can be of use for the /convert endpoint response as .. Actually, I don't know and I wish to know. Because processors.py do use the  serialiazed alias. However it seems these serialisation alias do end up in the final  collection of tokens output. WRONG:
The only reason `serialization_alias` exists here is **network payload compression and downstream collation efficiency**.

2. **Excluding Fields**: The `char_start` and `char_stop` fields are defined with `exclude=True`. Why are these character offsets needed during processing but explicitly excluded from the final JSON payload sent to the client?

**Answer:**
> 
The char offsets are needed for correct alignment of metadata post cltk analyze. However, these are not needed for further manipulation, therefore we don't sent it. the enriched converter append enriched  token without the offset thanks to the exlude true. otherwise, they would be added with the  enriched_token = Token(**token_dict). Also, we want to be clean and not send useless information to reduce load.

3. **Pydantic dumps**: In `converters.py`, `token.model_dump(by_alias=False, exclude_none=True)` is called. Why must `by_alias` be `False` when reconstructing the token after merging it with editorial metadata?

**Answer:**
> 
It's to be aligned with the processor. it filled it field using full names and not aliases. That's why.

## Section 3: NLP Processors
**Focus**: Linguistic processing, tokenization, and punctuation handling.

1. **Punctuation Merging**: Both `ClassicalProcessor` and `ModernProcessor` contain custom logic to handle tokens where `pos_tag == "PUNCT"`. Describe exactly what this logic does to the preceding token. What happens to the punctuation character itself?

**Answer:**
> 
so cltk.analyze creates a doc object containing words object. word contain information relative to the token, like the pos_tag. If one is PUNCT, we don't want to send it to the client as punctuation is noise. In greek and other language, punctuation didn't exist. They are most of the time added by the scribe and we want to filter  them. Therefore, we don't send a token of the punctuation, but we do link it in the "original" ("o") entry of the preceding token so that we have a trace of it.

2. **Normalization Strategies**: The `process` method accepts a `normalization` argument (e.g., `lemma`, `text`, `original`, `lemma+pos`). Trace how `lemma+pos` is constructed from a Stanza or CLTK word object. What happens if the `lemma` is missing from the underlying NLP library's output?

**Answer:**
> 
~Right now, the process and the Token class does expect lemma and pos from the analyse. cltk does give it and so does stanza. If this isn't possible for other language (smth else than greek or latin or cltk related language), than we would need to update the token construction in processor and forced fields in Token class. WRONG:
It's handled through the fallback word.string if word.lemma is None


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
