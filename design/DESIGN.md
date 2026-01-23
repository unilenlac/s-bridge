## Architecture
The actual and primary service request to be implemented is from the client to the Sigma API.
```mermaid
architecture-beta
    group Gateway[Portail API]
    group Api1[s_bridge server] in Gateway
    group Api2[Stemmarest server] in Gateway
    group Api3[DTS Server] in Gateway
    group Api4[Collatex server] in Gateway
    group Api5[Ollama Server] in Gateway

    service client(internet)[Stemmaweb client]

    service db1(database)[Database] in Api1
    service db2(database)[Database] in Api2
    

    service disk1(disk)[Storage]
    service disk2(disk)[Storage]
    service disk3(disk)[Storage]

    service server1(server)[App] in Api1
    service server2(server)[App] in Api2
    service server3(server)[App] in Api3
    service server4(server)[App] in Api4
    service server5(server)[App] in Api5

    db1:L -- R:server1
    db2:L -- R:server2
    

    disk1:L <-- R:db1
    disk2:L <-- R:db2
    disk3:R >-- L:server3

    server4{group}:T <--> B:server5{group}
    server3{group}:T <--> B:server4{group}
    server2{group}:T <--> B:server3{group}
    server1{group}:T <--> B:server2{group}
    
    client:B --> L:server1


```

## User Stories
- As a user, I want to create a new Tradition from a DTS collection URL so that I can analyze and compare different versions of a text.
- [Optional] As a user, I want to add a new section to an existing Tradition from a DTS collection URL so that I can expand the analysis of the text.
- As a user, I want to check the status of my requests so that I can monitor the progress of my Tradition creation or section addition.
- As a user, I want to cancel a running request so that I can stop the process if needed.

## Endpoints
#### Tradition endpoints
- /api/v1/tradition [GET] : list Traditions
- /api/v1/tradition [POST] : create a new Tradition from a DTS collection URL
- /api/v1/tradition/{id}/section [POST] : add a new section to an existing Tradition from a DTS collection URL
- /api/v1/tradition/{id} [GET] : get Tradition info [opt]
#### Request endpoints
- /api/v1/request [POST] : create a new create tradition Request
- /api/v1/request/{id} [GET] : get request status and results
- /api/v1/request/{id}/cancel [POST] : cancel a running request

## Definitions

#### variables :
- version = {id: txt, content: txt}
- tokenized_version = {id: txt, content: txt, tokens: list[Token]}
- Token = {t: txt, n : txt<lem+pos>}
- CiteStructure = short version of a DTS CiteStructure, ca be used to describe xml file navigation stored in a local storage
- **σ = list[Section<list[Version]>], a set of text version** = Tradition
- Tσ = list[Section<list[TokenizedVersion]>], a set of tokenized text version
- root = root element of a document = TokenizedTradition
- n = list[CiteStructure] = navigation
- section = n[x]
- docRef = main document in collection, serve as a reference

## Interaction Diagrams
#### General entities interaction (overview)
```mermaid
flowchart TB
    s[sigma]
    coll[CollateX]
    stmrst[Stemmarest]
    api[DTS API]
    stmwb[Stemmaweb Client]
    o[Ollama Client]

    stmwb--request create tradition from DTS url -->s
    coll--produces collation-->s
    s--sends collation to +<br/>create tradition-->stmrst
    stmrst--render tradition for-->stmwb
    s--send tokenized versions to-->coll
    s--create set of tokenized versions from-->api
    s--use Cltk/Ollama Client to analyse/tokenize texts-->o
```

#### API entities interaction
```mermaid
flowchart TB
    p[Pipeline/Chain]
    q[Queue]
    c[Client]
    dts[DTSClient]
    o[Ollama Client]
    t[Tokenizer/Analyzer]
    m[Request model]
    l[Logger]
    sc[Storage Client]
    c--initiate request-->q
    q--execute pipline tasks-->p
    p--use dts to get documents-->dts
    p--use tokenizer to process documents-->t
    p--use Request model to record request status-->m
    p--use Logger-->l
    t--use AI agent to analyse texts-->o
    p--use Storage Client to store σ object-->sc
```

#### DTSClient entities interaction
```mermaid
flowchart TB
    t[DTSClient]
    s[σ]
    v[Reference Version]
    d[XML Document]
    dts[DTS server]

    t--provide-->navigation
    t--provide-->d
    t--provide-->collection
    t--provide content for-->s

    d--content is provided by-->dts
    navigation--content is provided by-->dts
    v--content is provided by-->dts
    navigation--is provided by-->v
    collection--provide if necessary -->v
    collection--content is provided by-->dts
```

### Flows
#### Flow of a Request model when creating a Tradition
```mermaid
flowchart TB
    c[Client]
    m[Request model]
    p[Pipeline]
    q[Queue]
    ch[Checkout process]
    storage[Storage Client]
    scli[Stemmarest Client]

    c--initiate request-->m
    m-->id1{exists}
    id1--yes: abort-->c
    id1--else: enqueue request-->q
    q--execute pipline tasks-->p
    p--when done run checkout-->ch
    ch--check Request status-->id2{abort?}
    id2--yes-->abort[Abort process]
    id2--no: continue, save tradition-->scli
    scli--store σ set to local storage-->storage

    abort--update-->m
    storage--update-->m

```

## Sequences
### Create Tradition from a DTS Collection (overview)

```mermaid
sequenceDiagram
    actor c as Client
    participant s as Sigma API
    participant api as Data source (DTS)
    participant coll as Collatex API
    participant stmrst as Tradition Repo
    c->>s: create tradition from DTS collection
    s->>api: Build a set of document versions from Collection
    activate s
    api--)s: list[Version]
    activate s
    s->>s: Tokenize list[Version] -> list[TokenizedVersion]
    deactivate s
    deactivate s
    s->>coll:Build collation from list[TokenizedVersion]
    coll-->>s:collation<JSON>
    s->>stmrst:store tradition with collation
    stmrst--)s:request status
    s--)c:Success(200)

```

### Create Tradition from a DTS Collection (detailed)

```mermaid
sequenceDiagram
    actor c as Client
    participant s as Sigma API
    participant api as DTSClient
    participant agent as OllamaClient
    participant coll as CollatexClient
    participant stmrst as StemmarestClient
    participant db as Session
    participant storage as StorageClient
    participant logger as Logger
    c->>s: create tradition from DTS collection
    s->>logger: log request start
    activate s
    s->>db: init Request model
    db--)s: Request model
    s->>s: enqueue CreateTraditionWorker(Request)
    Note over s: asynchronous processing, errors are recorded with the Logger and the passed Request model
    s->>logger: log request enqueued
    s-)c:Accepted(202)
    s->>api: Build a set of document versions from Collection
    api--)s: list[Version]
    s->>agent: Analyze/tokenize list[Version]
    agent--)s: list[TokenizedVersion]

    s->>coll:Build collation from list[TokenizedVersion]
    coll-->>s:collation<JSON>
    s->>db: refresh Request model status
    db--)s: Request model
    alt Request not aborted
        Note over s, storage: Checkout process
        activate s
        s->>stmrst:store tradition with collation
        stmrst--)s: Tradition stored
        s->>storage:store σ set
        storage--)s:storage message
        s->>db: save Tradition to DB along storage client result info
        deactivate s
    end
    s-)logger: log request completion
    deactivate s

```

### update Tradition with a new Section from a DTS Collection
```mermaid
sequenceDiagram
    actor c as Client
    participant s as Sigma
    participant api as DTSClient
    participant agent as OllamaClient
    participant coll as CollatexClient
    participant stmrst as StemmarestClient
    participant db as Session
    participant storage as StorageClient
    participant logger as Logger
    c->>s: update tradition with new analysis <br/>(Tradition id, DTS collection URL, section xml:id)
    s->>db: get Tradition by id
    db--)s: Tradition
    alt Tradition found
        s->>storage: get σ set with Tradition.storage_info
        storage--)s: σ set
    else
        s--)c: NotFound(404)
    end
    s->>db: init Request(type="add section") model
    db--)s: Request model
    s-)logger: log request enqueued
    s--)c:Accepted(202)
    activate s
    s->>s: enqueue AddSectionToTraditionWorker(Request, Tradition, σ set)
    Note over s: asynchronous processing, errors are recorded with the Logger and the passed Request model
    s->>api: extend σ set with a new section from DTS URL
    api--)s: extended list[Version]
    s->>agent: Analyze/tokenize extended σ[section]
    agent--)s: list[TokenizedVersion]
    s->>coll:Build new collation from list[TokenizedVersion]
    coll-->>s:new Collation<JSON>
    s->>s: get section from Collation
    s->>db: refresh Request model status
    db--)s: Request model
    alt Request not aborted
        Note over s, storage: Checkout process
        activate s
        s->>stmrst: update tradition with collation
        stmrst--)s: Tradition stored
        s->>storage:store σ set
        storage--)s:storage message
        s->>db: update Tradition infos to DB
        deactivate s
    end
    s-)logger: log request completion
    deactivate s
```

note: there is no way to update a section with a new witness graph right now in Stemmarest API. Todo: add into the Stemmarest API, an update section endpoint to allow this.

## Classes & Entities
### Task classes (chain of responsibility pattern)

```mermaid
classDiagram
    class Task~ABC~{
        + setNext(task: Task): void
        + execute(request: Request): void
    }
    class AbsTask{
        - nextTask: Task
        + setNext(task: Task): void
        + execute(request: Request): void
        + passToNext(request: Request): void
    }
    class BuildSigmaSetTask{
        + store: DTSClient
        + parser: Parser
        + execute(request: Request): void
    }
    class AnalyseAndTokenizeTask{
        + agent: OllamaClient
        + execute(request: Request): void
    }
    class BuildCollationTask{
        + collatex: CollatexClient
        + execute(request: Request): void
    }
    class CheckoutTask{
        + stemmarest: StemmarestClient
        + storage: StorageClient
        + execute(request: Request): void
    }
    class Request{
        + set: list[Section<list[Version|TokenizedVersion]>]
        + task_request: TaskRequest
    }
    class TaskRequest{
        + id: int
        + date_created: datetime
        + date_updated: datetime
        + type: str
        + status: str
        + tradition_id: int
        + dts_url: str
        + section_path: str
    }
    Request --> TaskRequest
    Task <|.. AbsTask
    AbsTask <|.. BuildSigmaSetTask
    AbsTask <|.. AnalyseAndTokenizeTask
    AbsTask <|.. BuildCollationTask
    AbsTask <|.. CheckoutTask
```

#### Pipeline Builder classes (builder pattern)
```mermaid
    classDiagram
    class PipelineSelector{
        builder: PipelineBuilder
        +make_pipeline(name: str): void
        +get_result(): Set
    }
    class PipelineBuilder~interface~{
        +reset
        +compose(): Task
        +analyse(): Task
        +collate(): Task
        +checkout(): Task
    }
    class DTSPipelineBuilder{
        +chain: Task
        +reset
        +compose(): Task
        +analyse(): Task
        +collate(): Task
        +checkout(): Task
    }
    PipelineSelector --> PipelineBuilder
    PipelineBuilder <|.. DTSPipelineBuilder
```

## AnalysisClient Specifications
The Analysis Client is a module that allows interaction with an AI agent server to perform NLP tasks such as tokenization, lemmatization, and POS tagging. It is designed to be used within the σ-Bridge application to process text versions retrieved from DTS collections.

Ideally the client should also rely on a local nlp processor in case that a remote server is not available.

Ideally the result should include a Docker image of the selected NLP server that can be deployed alongside the σ-Bridge API.

### Features
- Connect to a local server using a specified host and port.
- Send text data to the server for processing.
- Receive and parse the processed output from the server.
- Handle errors and exceptions during communication with the server.

### input/output specifications
- Input: raw text string to be analyzed. Can contain special characters or elements like html elements, punctuation, and whitespace.

example: 

```python 
Hello, world! <hi />This is a test.
```

- Output: a dictionary containing the analyzed data, including tokens, lemmas, and POS tags. Punctuation and special elements should be preserved in the output but not tokenized. Punctuation are merged with the preceding token original value in the 'original' field.

example:

```JSON
{
    "tokens": [
        {"t": "Hello", "n": "hello+INTJ", "original": "hello,", "lem": "hello", "pos": "INTJ"},
        {"t": "world", "n": "world+NOUN", "original": "world !", "lem": "world", "pos": "NOUN"},
        {"t": "<hi />", "n": "", "lem": "<hi />", "pos": "SYM"},
        {"t": "This", "n": "this+PRON", "original": "this"},
        {"t": "is", "n": "is+VERB", "lem": "be", "pos": "VERB"},
        {"t": "a", "n": "a+DET", "lem": "a", "pos": "DET"},
        {"t": "test", "n": "test+NOUN", "lem": "test", "pos": "NOUN"},
        {"t": ".", "n": "", "lem": ".", "pos": "PUNCT"}
    ]
}
```

### constraints
- input text language should primarily be Ancient Greek, but the client should be flexible enough to handle other languages if needed.

### Class Diagram
```mermaid
classDiagram
    class AnalysisClient~ABC~{
        - host: str
        - port: int
        + __init__(host: str, port: int): void
    }
    class OllamaClient{
        + analyze_text(text: str): dict
    }
    AnalysisClient <|.. OllamaClient
```

### entities interaction
```mermaid
flowchart TB
    a[AnalysisClient]
    s[Ollama Server]
    a--send text to analyze-->s
    s--return analyzed data-->a
    a--process result-->a
    a--return processed data-->s-bridge
```

### Resources:

Original processing can be found in the old xml2stemmarest repo [here](https://github.com/unilenlac/xml2stemmarest/blob/main/shell-scripts/xml2stemmarest.sh)

### suggested dependencies
- cltk
- spacy
