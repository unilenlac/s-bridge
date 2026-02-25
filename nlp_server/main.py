from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import logging

app = FastAPI(title="σ-Bridge NLP Server", description="Remote NLP parsing service using CLTK")
logger = logging.getLogger("nlp_server")

# Global NLP instance
nlp = None

class AnalyzeRequest(BaseModel):
    text: str
    lang: str = "grc"
    # Optional parameters for token format (e.g. lemma+pos)
    n_format: str = "lemma+pos"

@app.on_event("startup")
async def startup_event():
    global nlp
    logger.info("Initializing CLTK NLP engine...")
    from cltk import NLP
    from contextlib import redirect_stdout, redirect_stderr
    import io
    
    # Suppress CLTK startup noise
    f = io.StringIO()
    with redirect_stdout(f), redirect_stderr(f):
         nlp = NLP("grc", backend="stanza", suppress_banner=True)
    logger.info("CLTK NLP engine initialized successfully.")

def build_tokens_json(doc, n_format: str) -> List[Dict[str, Any]]:
    tokens = []
    
    for word in doc.words:
        pos_tag = word.upos.tag if word.upos else "UNKNOWN"
        
        if pos_tag == "PUNCT":
            if tokens:
                tokens[-1]["original"] += word.string
            continue
            
        # Safely extract linguistic features (like Case, Gender, Number) if they exist
        feats_dict = {}
        if hasattr(word, 'features') and word.features and hasattr(word.features, 'features'):
            for tag in word.features.features:
                feats_dict[tag.key] = tag.value
            
        lemma = word.lemma if getattr(word, 'lemma', None) is not None else word.string
        
        if n_format == "original":
            n_val = word.string
        elif n_format == "lemma":
            n_val = lemma
        else: # Handle all + configurations
            parts = n_format.split('+')
            n_components = []
            if "lemma" in parts: n_components.append(lemma)
            elif "original" in parts: n_components.append(word.string)
            if "pos" in parts: n_components.append(pos_tag)
            if "cgn" in parts:
                if feats_dict.get("Case"): n_components.append(feats_dict.get("Case"))
                if feats_dict.get("Gender"): n_components.append(feats_dict.get("Gender"))
                if feats_dict.get("Number"): n_components.append(feats_dict.get("Number"))
            n_val = "+".join(n_components)
            
        tokens.append({
            "t": word.string,
            "n": n_val,
            "original": word.string,
            "lem": lemma,
            "pos": pos_tag,
            "case": feats_dict.get("Case"),
            "gender": feats_dict.get("Gender"),
            "num": feats_dict.get("Number")
        })
        
    return tokens

@app.post("/analyze")
async def analyze_text(request: AnalyzeRequest):
    if not request.text.strip():
        return {"tokens": []}
        
    if request.lang != "grc":
        raise HTTPException(status_code=400, detail="Only 'grc' (Ancient Greek) is currently supported on this server instance.")
        
    try:
        # Run synchronous CLTK analysis
        doc = nlp.analyze(request.text)
        tokens = build_tokens_json(doc, request.n_format)
        return {"tokens": tokens}
    except Exception as e:
        logger.error(f"NLP analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Internal NLP Error: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "ok", "engine": "cltk", "lang": "grc"}
