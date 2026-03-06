# `s-bridge/nlp_server` Learning Exercises

These exercises are designed to test your understanding of the core architectural concepts and tools we've implemented in this repository. They are split into theoretical questions and practical tasks. 

Try to answer the theoretical questions in your own words. For the practical tasks, feel free to write the code in a scratchpad file or directly in the repo, and we can review the implementation together!

---

## 1. Architecture & Dependency Injection (FastAPI)

We structured the `/convert` endpoint to be entirely decoupled from the concrete implementations of the parser and processor.

### Theoretical Questions
1. **The Magic Behind the Endpoint:** Look at the `convert` function in `main.py`. It requires a `converter: Converter` argument. How does FastAPI automatically know which converter (e.g., `SimpleConverter` vs. `FullConverter`) to provide when you hit the `/convert` endpoint? Explain the mechanism linking `converter: Converter` and `processor_dep.py`.



2. **Switching Contexts:** In `processor_dep.py`, what is the exact function of the `mode` query parameter? If a user sends a request to `/convert?mode=full`, what happens behind the scenes during the dependency generation?

### Practical Task
* **Add a Status Endpoint:** In `main.py`, create a new simple `GET` endpoint at `/status`. Use FastAPI dependency injection (or directly access `request.app.state`) to return a JSON response indicating which NLP pipeline engine (Classical vs. Modern) is currently instantiated and loaded in the application state.

---

## 2. Interfaces & Protocols (Duck Typing)

We utilized `typing.Protocol` extensively in `interfaces.py` rather than traditional inheritance (like `class TEIParser(Parser):`).

### Theoretical Questions
1. **Implicit vs. Explicit:** Why did we choose `typing.Protocol` for `Parser`, `Processor`, and `Converter`? 
2. **The Contract:** Suppose you write a completely new class, `EADParser`, that parses Archival XML instead of TEI. If you do *not* explicitly make it inherit from `Parser`, but you do give it a `.parse(self, data: ET.Element)` method, will it still satisfy the `Parser` protocol requirements for `FullConverter`? Why or why not?

### Practical Task
* **Proving the Protocol:** Create a quick dummy class called `EADParser` (in a scratch file or anywhere convenient). 
    * Give it a `.parse(self, data: ET.Element)` method that simply returns a hardcoded string `("test", [])`.
    * Temporarily modify `processor_dep.py` (or a test file) to instantiate `FullConverter` passing in your `EADParser` instead of `TEIParser`. 
    * Verify that type checkers (or Python at runtime) do not throw errors regarding the interface.

---

## 3. Data Models & Pydantic

We use `pydantic` heavily in `collatex.py` to structure our `Token` objects. 

### Theoretical Questions
1. **Merging Data:** In `Converters.py`, specifically inside `FullConverter.run()`, we use `token.model_dump(by_alias=True, exclude_none=True)` to convert the Pydantic model into a dictionary before updating it with TEI metadata. Why is `exclude_none=True` particularly important here before we re-instantiate the completely enriched `Token`?

### Practical Task
* **Expanding the Model:** We want to start tracking named entities. 
    * Open `collatex.py` and modify the `Token` model to include a new, optional boolean field: `is_named_entity`.
    * Open `Converters.py` and modify the `SimpleConverter` so that it sets this new property to `False` for all tokens it returns.

---

## 4. XML Parsing (ElementTree)

We migrated from `BeautifulSoup` to Python's native `xml.etree.ElementTree` because it handles mixed-content XML far more gracefully.

### Theoretical Questions
1. **Text vs. Tail:** Explain the critical difference between `element.text` and `element.tail` in ElementTree when processing a string like `This is some <hi>bold</hi> text.`. Why was ignoring `.tail` the root cause of our previous parsing bugs?

### Practical Task
* **Extracting Specifics:** Write a short standalone python script (or a new test function) that imports `xml.etree.ElementTree`.
    * Use `ET.fromstring()` to parse the `dummy_data` string found in `main.py`.
    * Write a few lines of code to iterate through the resulting ElementTree, find specifically the `<seg>` tags, and print their raw `.text` content.

---

## 5. The Application Lifecycle

### Theoretical Question
1. **Lifespan Context:** Look at the `@asynccontextmanager def lifespan(app: FastAPI):` function in `main.py`. Why do we load the NLP models (Stanza/CLTK) inside this lifespan function instead of loading them globally outside the app, or instantiating them directly inside the `/convert` endpoint upon receiving a request?
