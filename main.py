from cltk import NLP

    
def main():
    nlp = NLP("lati1261", backend="stanza",  suppress_banner=True)
    doc = nlp.analyze("Gallia est omnis divisa in partes tres.")
    for w in doc.words[:10]:
        print(w.string, getattr(w.upos, "tag", None), w.lemma)



if __name__ == "__main__":
    main()
