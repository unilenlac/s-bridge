# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "cltk",
#   "cltk[stanza]",
#   "requests",
#   "rich",
# ]
# ///

from cltk import NLP
nlp = NLP("lati1261", backend="stanza",  suppress_banner=True)
doc = nlp.analyze("Gallia est omnis divisa in partes tres.")
for w in doc.words[:10]:
    print(w.string, getattr(w.upos, "tag", None), w.lemma)