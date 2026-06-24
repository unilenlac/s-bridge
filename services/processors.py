from typing import Any
from stanza import Pipeline
from models.tokenization import Token


class ClassicalProcessor:
    def __init__(self, pipeline: Any):
        # Initialize any necessary resources for processing Greek text
        self.pipeline = pipeline

    def process(self, data, normalization="lemma"):
        # Run the NLP pipeline
        cltk_doc = self.pipeline.analyze(data)

        # Convert the CLTK objects into our generic Token objects
        tokens = []
        for word in cltk_doc.words:
            pos_tag = word.upos.tag if word.upos else "UNKNOWN"

            w_start = getattr(word, "index_char_start", None)
            w_stop = getattr(word, "index_char_stop", None)

            if pos_tag == "PUNCT":
                if tokens:
                    prev = tokens[-1]
                    can_merge = False
                    if prev.char_stop is not None and w_start is not None:
                        if prev.char_stop == w_start:
                            can_merge = True
                    else:
                        can_merge = True

                    if can_merge:
                        if prev.char_start is not None and w_stop is not None:
                            prev.char_stop = w_stop
                            prev.original = data[prev.char_start : w_stop]
                        else:
                            prev.original += word.string
                        continue

            # Safely extract NLP features (Case, Gender, Number)
            feats_dict = {}
            if (
                hasattr(word, "features")
                and word.features
                and hasattr(word.features, "features")
            ):
                for tag in word.features.features:
                    feats_dict[tag.key] = tag.value

            lemma_raw = (
                word.lemma if getattr(word, "lemma", None) is not None else word.string
            )

            if normalization == "lemma":
                norm_str = lemma_raw
            elif normalization == "text":
                norm_str = word.string
            else:
                norm_str = f"{lemma_raw}+{pos_tag}"

            # Build our clean data model (NO string formatting!)
            # NOTE: We add a trailing space to 'text' (t) for better display in CollateX graphs,
            # while 'normalization' (n) remains clean for precise alignment.
            my_token = Token(
                text=word.string + " ",
                normalization=norm_str,
                original=word.string,
                lemma=lemma_raw,
                pos=pos_tag,
                cs=feats_dict.get("Case"),
                gender=feats_dict.get("Gender"),
                number=feats_dict.get("Number"),
                char_start=w_start,
                char_stop=w_stop,
            )
            tokens.append(my_token)

        return tokens


class ModernProcessor:
    def __init__(self, pipeline: Pipeline):
        # Initialize any necessary resources for processing modern text
        self.pipeline = pipeline

    def process(self, data, normalization="lemma"):
        stanza_doc = self.pipeline(data)
        tokens = []
        for sentence in stanza_doc.sentences:
            for word in sentence.words:
                pos_tag = word.upos if word.upos else "UNKNOWN"

                w_start = (
                    getattr(
                        word.parent, "start_char", getattr(word, "start_char", None)
                    )
                    if hasattr(word, "parent")
                    else getattr(word, "start_char", None)
                )
                w_stop = (
                    getattr(word.parent, "end_char", getattr(word, "end_char", None))
                    if hasattr(word, "parent")
                    else getattr(word, "end_char", None)
                )

                if pos_tag == "PUNCT":
                    if tokens:
                        prev = tokens[-1]
                        can_merge = False
                        if prev.char_stop is not None and w_start is not None:
                            if prev.char_stop == w_start:
                                can_merge = True
                        else:
                            can_merge = True

                        if can_merge:
                            if prev.char_start is not None and w_stop is not None:
                                prev.char_stop = w_stop
                                # We artificially expend the previous token's bounding box
                                prev.original = data[prev.char_start : w_stop]
                            else:
                                prev.original += word.text
                            continue

                # Safely extract NLP features (Stanza stores them as string: 'Case=Nom|Gender=Masc|Number=Sing')
                feats_dict = {}
                if word.feats:
                    for feat in word.feats.split("|"):
                        if "=" in feat:
                            key, value = feat.split("=", 1)
                            feats_dict[key] = value

                lemma_raw = (
                    word.lemma
                    if getattr(word, "lemma", None) is not None
                    else word.text
                )

                if normalization == "lemma":
                    norm_str = lemma_raw
                elif normalization == "text":
                    norm_str = word.text
                else:
                    norm_str = f"{lemma_raw}+{pos_tag}"

                # Build our clean data model (NO string formatting!)
                # NOTE: We add a trailing space to 'text' (t) for better display in CollateX graphs,
                # while 'normalization' (n) remains clean for precise alignment.
                my_token = Token(
                    text=word.text + " ",
                    normalization=norm_str,
                    original=word.text,
                    lemma=lemma_raw,
                    pos=pos_tag,
                    cs=feats_dict.get("Case"),
                    gender=feats_dict.get("Gender"),
                    number=feats_dict.get("Number"),
                    char_start=w_start,
                    char_stop=w_stop,
                )
                tokens.append(my_token)

        return tokens


class RawProcessor:
    def __init__(self, pipeline: Any = None):
        pass

    def process(self, data: str, normalization: str = "text") -> list[Token]:
        words = data.split()
        tokens = []
        for word in words:
            tokens.append(
                Token(
                    text=word + " ",
                    normalization=word,
                    original=word,
                    lemma="",
                )
            )
        return tokens

