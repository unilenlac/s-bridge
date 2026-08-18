import pytest
from helpers.helpers import strip_accents
from services.processors import RawProcessor, ClassicalProcessor, ModernProcessor
from models.tokenization import Token


def test_strip_accents_polytonic_greek():
    # Basic word forms from chapter 142 and common Greek variants
    assert strip_accents("ὅτε") == "οτε"
    assert strip_accents("δὲ") == "δε"
    assert strip_accents("ἐπλήρωσεν") == "επληρωσεν"
    assert strip_accents("τὴν") == "την"
    assert strip_accents("τὸν") == "τον"
    assert strip_accents("τοῦ") == "του"
    assert strip_accents("ἐπαγγελίαν") == "επαγγελιαν"
    assert strip_accents("ταύτην") == "ταυτην"
    assert strip_accents("ὁ") == "ο"
    assert strip_accents("φίλιππος") == "φιλιππος"
    assert strip_accents("Φίλιππος,") == "φιλιππος"
    assert strip_accents("λέγει") == "λεγει"
    assert strip_accents("αὐτοῖς·") == "αυτοις"
    assert strip_accents("λύσατε") == "λυσατε"
    assert strip_accents("βαρθολομαῖον·") == "βαρθολομαιον"
    assert strip_accents("Βαρθολομαίον") == "βαρθολομαιον"
    assert strip_accents("καὶ") == "και"
    assert strip_accents("καί") == "και"
    assert strip_accents("ἔλυσαν") == "ελυσαν"
    assert strip_accents("αὐτόν") == "αυτον"
    assert strip_accents("αὐτὸν·") == "αυτον"
    assert strip_accents("προσελθόντες") == "προσελθοντες"


def test_strip_accents_complex_diacritics():
    # Breathing + circumflex, iota subscript, diaeresis, Greek punctuation
    assert strip_accents("ἆρα") == "αρα"
    assert strip_accents("ᾖ") == "η"
    assert strip_accents("ᾠδή") == "ωδη"
    assert strip_accents("ῥῆμα") == "ρημα"
    assert strip_accents("πραΰς") == "πραυς"
    assert strip_accents("«λόγος»·") == "λογος"
    assert strip_accents("—τίς;") == "τις"


def test_strip_accents_empty_and_whitespace():
    assert strip_accents("") == ""
    assert strip_accents("   ") == ""


def test_raw_processor_baseline_unaccented():
    proc = RawProcessor()
    text = "ὅτε δὲ ἐπλήρωσεν τὴν ἐπαγγελίαν ταύτην ὁ φίλιππος"
    tokens = proc.process(text)

    assert len(tokens) == 8
    assert tokens[0].normalization == "οτε"
    assert tokens[0].text == "ὅτε "
    assert tokens[0].original == "ὅτε"
    assert tokens[1].normalization == "δε"
    assert tokens[2].normalization == "επληρωσεν"
    assert tokens[3].normalization == "την"
    assert tokens[4].normalization == "επαγγελιαν"
    assert tokens[5].normalization == "ταυτην"
    assert tokens[6].normalization == "ο"
    assert tokens[7].normalization == "φιλιππος"


def test_classical_processor_baseline_unaccented_lemma():
    class DummyUpos:
        def __init__(self, tag):
            self.tag = tag

    class DummyWord:
        def __init__(self, string, upos="NOUN", lemma="dummy", stem=None):
            self.string = string
            self.upos = DummyUpos(upos)
            self.lemma = lemma
            self.stem = stem or lemma
            self.index_char_start = 0
            self.index_char_stop = len(string)
            self.features = None

    class DummyDoc:
        def __init__(self, words):
            self.words = words

    class DummyPipeline:
        def analyze(self, text):
            return DummyDoc(
                [
                    DummyWord("ὅτε", upos="SCONJ", lemma="ὅτε"),
                    DummyWord("δὲ", upos="ADV", lemma="δέ"),
                    DummyWord("τὴν", upos="DET", lemma="ὁ"),
                    DummyWord("ἐπαγγελίαν", upos="NOUN", lemma="ἐπαγγελία"),
                    DummyWord("βαρθολομαῖον", upos="NOUN", lemma="βαρθολομαῖος"),
                ]
            )

    proc = ClassicalProcessor(pipeline=DummyPipeline())

    # 1. Default (lemma normalization)
    tokens = proc.process("dummy text", normalization="lemma")
    assert len(tokens) == 5
    assert tokens[0].normalization == "οτε"
    assert tokens[0].normal_form == "οτε"
    assert tokens[0].lemma == "ὅτε"
    assert tokens[1].normalization == "δε"
    assert tokens[1].normal_form == "δε"
    assert tokens[1].lemma == "δέ"
    # Determinant/article "τὴν" normalizes to its unaccented lemma "ὁ" -> "ο"
    assert tokens[2].normalization == "ο"
    assert tokens[2].normal_form == "ο"
    assert tokens[2].lemma == "ὁ"
    assert tokens[3].normalization == "επαγγελια"
    assert tokens[3].normal_form == "επαγγελια"
    assert tokens[3].lemma == "ἐπαγγελία"
    assert tokens[4].normalization == "βαρθολομαιος"
    assert tokens[4].normal_form == "βαρθολομαιος"
    assert tokens[4].lemma == "βαρθολομαῖος"

    # 2. Text normalization
    tokens_text = proc.process("dummy text", normalization="text")
    assert tokens_text[0].normalization == "οτε"
    assert tokens_text[3].normalization == "επαγγελιαν"
    assert tokens_text[4].normalization == "βαρθολομαιον"

    # 3. Lemma+pos normalization
    tokens_pos = proc.process("dummy text", normalization="lemma+pos")
    assert tokens_pos[0].normalization == "οτε+SCONJ"
    assert tokens_pos[3].normalization == "επαγγελια+NOUN"


def test_modern_processor_baseline_unaccented():
    class DummyWord:
        def __init__(self, text, upos="NOUN", lemma="dummy", stem=None):
            self.text = text
            self.upos = upos
            self.lemma = lemma
            self.stem = stem or lemma
            self.feats = ""
            self.start_char = 0
            self.end_char = len(text)

    class DummySentence:
        def __init__(self, words):
            self.words = words

    class DummyDoc:
        def __init__(self, sentences):
            self.sentences = sentences

    class DummyPipeline:
        def __call__(self, text):
            return DummyDoc(
                [
                    DummySentence(
                        [
                            DummyWord("Éléphant", upos="NOUN", lemma="éléphant"),
                            DummyWord("très", upos="ADV", lemma="très"),
                            DummyWord("âgé", upos="ADJ", lemma="âgé"),
                        ]
                    )
                ]
            )

    proc = ModernProcessor(pipeline=DummyPipeline())
    tokens = proc.process("dummy text", normalization="lemma")

    assert len(tokens) == 3
    assert tokens[0].normalization == "elephant"
    assert tokens[0].text == "Éléphant "
    assert tokens[0].lemma == "éléphant"
    assert tokens[1].normalization == "tres"
    assert tokens[2].normalization == "age"
