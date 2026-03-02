from typing import Any
from stanza import Pipeline
from nlp_server.model.collatex import Token

class ClassicalProcessor:
    def __init__(self, pipeline: Any):
        # Initialize any necessary resources for processing Greek text
        self.pipeline = pipeline
    def process(self, data):
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
            
            # Build our clean data model (NO string formatting!)
            my_token = Token(
                text=word.string,
                lemma=word.lemma if getattr(word, 'lemma', None) is not None else word.string,
                original=word.string,
                pos=word.upos.tag if word.upos else "UNKNOWN",
                cs=feats_dict.get("Case"),
                gender=feats_dict.get("Gender"),
                number=feats_dict.get("Number"),
                # We leave XML metadata blank. The Converter fills that in!
                unclear=False,
                add=False,
                abbr=False
            )
            tokens.append(my_token)
            
        return tokens

class ModernProcessor:
    def __init__(self, pipeline: Pipeline):
        # Initialize any necessary resources for processing modern text
        self.pipeline = pipeline
    def process(self, data):
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
                
                # Build our clean data model (NO string formatting!)
                my_token = Token(
                    text=word.text,
                    lemma=word.lemma if getattr(word, 'lemma', None) is not None else word.text,
                    original=word.text,
                    pos=pos_tag,
                    cs=feats_dict.get("Case"),
                    gender=feats_dict.get("Gender"),
                    number=feats_dict.get("Number"),
                    # We leave XML metadata blank. The Converter fills that in!
                    unclear=False,
                    add=False,
                    abbr=False
                )
                tokens.append(my_token)
                
        return tokens