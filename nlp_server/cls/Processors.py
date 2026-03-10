from typing import Any
from stanza import Pipeline
from nlp_server.model.collatex import Token

class ClassicalProcessor:
    def __init__(self, pipeline: Any):
        # Initialize any necessary resources for processing Greek text
        self.pipeline = pipeline
    def process(self, data, normalization="lemma+pos"):
        # Run the NLP pipeline
        cltk_doc = self.pipeline.analyze(data)

        # Convert the CLTK objects into our generic Token objects
        tokens = []
        for word in cltk_doc.words:
            pos_tag = word.upos.tag if word.upos else "UNKNOWN"
            
            if pos_tag == "PUNCT":
                if tokens:
                    tokens[-1].original += word.string
                continue

            # Safely extract NLP features (Case, Gender, Number)
            feats_dict = {}
            if hasattr(word, 'features') and word.features and hasattr(word.features, 'features'):
                for tag in word.features.features:
                    feats_dict[tag.key] = tag.value
            
            lemma_raw = word.lemma if getattr(word, 'lemma', None) is not None else word.string
            
            if normalization == "lemma":
                norm_str = lemma_raw
            elif normalization == "text":
                norm_str = word.string
            elif normalization == "original":
                norm_str = word.string
            else:
                norm_str = f"{lemma_raw}+{pos_tag}"
            
            # Build our clean data model (NO string formatting!)
            my_token = Token(
                text=word.string,
                normalisation=norm_str,
                original=word.string,
                lemma=lemma_raw,
                pos=pos_tag,
                cs=feats_dict.get("Case"),
                gender=feats_dict.get("Gender"),
                number=feats_dict.get("Number")
            )
            tokens.append(my_token)
            
        return tokens

class ModernProcessor:
    def __init__(self, pipeline: Pipeline):
        # Initialize any necessary resources for processing modern text
        self.pipeline = pipeline
    def process(self, data, normalization="lemma+pos"):
        stanza_doc = self.pipeline(data)
        tokens = []
        for sentence in stanza_doc.sentences:
            for word in sentence.words:
                pos_tag = word.upos if word.upos else "UNKNOWN"
                
                if pos_tag == "PUNCT":
                    if tokens:
                        tokens[-1].original += word.text
                    continue

                # Safely extract NLP features (Stanza stores them as string: 'Case=Nom|Gender=Masc|Number=Sing')
                feats_dict = {}
                if word.feats:
                    for feat in word.feats.split('|'):
                        if '=' in feat:
                            key, value = feat.split('=', 1)
                            feats_dict[key] = value
                
                lemma_raw = word.lemma if getattr(word, 'lemma', None) is not None else word.text
                
                if normalization == "lemma":
                    norm_str = lemma_raw
                elif normalization == "text":
                    norm_str = word.text
                elif normalization == "original":
                    norm_str = word.text
                else:
                    norm_str = f"{lemma_raw}+{pos_tag}"
                
                # Build our clean data model (NO string formatting!)
                my_token = Token(
                    text=word.text,
                    normalisation=norm_str,
                    original=word.text,
                    lemma=lemma_raw,
                    pos=pos_tag,
                    cs=feats_dict.get("Case"),
                    gender=feats_dict.get("Gender"),
                    number=feats_dict.get("Number")
                )
                tokens.append(my_token)
                
        return tokens