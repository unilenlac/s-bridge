from .analysis import AnalysisClient
from contextlib import redirect_stdout, redirect_stderr
import os
import io
import sys
from typing import Dict, Any, List

class LocalCltkClient(AnalysisClient):
    """Local client that processes NLP directly using CLTK in-memory. Useful for fallback or testing without a server."""
    
    def __init__(self, host: str = "localhost", port: int = 0, lang: str = "grc", backend: str = "stanza",  n_format: str = "lemma+pos"):
        super().__init__(host, port)
        self.n_format = n_format
        
        # Suppress output from CLTK during initialization
        import logging
        logging.getLogger('cltk').setLevel(logging.ERROR)
        logging.getLogger('stanza').setLevel(logging.ERROR)
        
        # We lazily import CLTK so we don't pay the import cost if this client isn't used
        from cltk import NLP
        
        # Stanza downloads trigger a lot of stdout output, we redirect it briefly
        f = io.StringIO()
        with redirect_stdout(f), redirect_stderr(f):
             self.nlp = NLP(lang, backend=backend, suppress_banner=True)

    def _build_collatex_tokens(self, doc) -> List[Dict[str, Any]]:
        """Internal logic to convert CLTK Doc to JSON serializable dictionaries."""
        collatex_payloads: List[Dict[str, Any]] = []
        n_format = self.n_format
        
        for word in doc.words:
            pos_tag = word.upos.tag if word.upos else "UNKNOWN"
            
            if pos_tag == "PUNCT":
                if collatex_payloads:
                    collatex_payloads[-1]["original"] += word.string
                continue
            
            # Safely extract linguistic features (like Case, Gender, Number) if they exist
            feats_dict = {}
            if hasattr(word, 'features') and word.features:
                for tag in word.features:
                    feats_dict[tag.key] = tag.value
            
            lemma = word.lemma if getattr(word, 'lemma', None) is not None else word.string
            
            if n_format == "original":
                n_val = word.string
            elif n_format == "lemma":
                n_val = lemma
            else: # Handle all + configurations
                parts = n_format.split('+')
                n_components = []
                
                if "lemma" in parts:
                    n_components.append(lemma)
                elif "original" in parts:
                    n_components.append(word.string)
                    
                if "pos" in parts:
                    n_components.append(pos_tag)
                    
                if "cgn" in parts:
                    case = feats_dict.get("Case")
                    gender = feats_dict.get("Gender")
                    num = feats_dict.get("Number")
                    if case: n_components.append(case)
                    if gender: n_components.append(gender)
                    if num: n_components.append(num)
                    
                n_val = "+".join(n_components)
            
            token_data: Dict[str, Any] = {
                "t": word.string,
                "n": n_val,
                "original": word.string,
                "lem": lemma,
                "pos": pos_tag,
                "case": feats_dict.get("Case"),
                "gender": feats_dict.get("Gender"),
                "num": feats_dict.get("Number")
            }
            
            # Note: We do NOT append editorial metadata here. AnalysisClient only returns NLP data.
            # tokenize_xml.py is responsible for aligning the metadata_map with the returned generic tokens.
            
            collatex_payloads.append(token_data)
        
        return collatex_payloads

    def analyze_text(self, text: str) -> List[Dict[str, Any]]:
        if not text.strip():
             return []
        
        doc = self.nlp.analyze(text)
        return self._build_collatex_tokens(doc)
