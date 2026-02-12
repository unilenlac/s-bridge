from cltk import NLP
import requests
from bs4 import BeautifulSoup

def keep_metadata(void):
    # Here is an attempt at storing TEI meta data so that the intel is not lost to
    # the nlp analysis. Each line is read, analysed and metadata stored.
    # I am not yet sure it is usefull. Maybe nlp + collate is enough.

    all_docs: list = []

    for l_tag in soup.find_all("l"):
        # Create a Doc for a specific TEI line
        line_doc = nlp.analyze(l_tag.get_text())

        # Store the TEI line number at the Doc level (where metadata IS allowed)
        line_doc.metadata = {"tei_ref": l_tag.get("n")}  #

        for word in line_doc.words:
            # Use 'enrichment' for token-specific TEI info like <unclear> or <supplied>
            if l_tag.find("supplied"):
                word.enrichment = {"tei_status": "supplied"}  #

            # Use 'annotation_sources' to track that this token came from a DTS fragment
            word.annotation_sources = {"source": "DTS_Response"}  #

        all_docs.append(line_doc)

def main():
    url: str = "https://dts.perseids.org/documents"
    params: str = {
        "id": "urn:cts:greekLit:tlg0012.tlg001.perseus-grc2",
        "start": "1.1",
        "end": "1.5"
    }
    response: str = requests.get(url, params=params)

    text_to_process: str = response.text

    print(text_to_process)

    # Use the 'xml' parser specifically for TEI
    soup : bs4.BeautifulSoup = BeautifulSoup(text_to_process, features="xml")

    print(soup.prettify())

    nlp = NLP("grc", backend="stanza", suppress_banner=True)

    # 1. Target the fragment/wrapper
    # We use find() because 'dts:fragment' is the container for the text chunk
    fragment = soup.find("dts:fragment") or soup.find("fragment")

    if fragment:
        # 2. Get text with a space separator
        # This ensures "Ἀχιλῆος" and "οὐλομένην" don't get merged into one word
        greek_text = fragment.get_text(separator=" ", strip=True)

        # 3. Clean up extra whitespace/newlines for the NLP
        clean_greek = " ".join(greek_text.split())

        print(clean_greek + '\n')

        doc = nlp.analyze(clean_greek)
        for sentence in doc.sentences:
            for word in sentence.words:
                print(f"Token: {word.string:<15} | Lemma: {word.lemma:<15} | POS: {word.upos}")

if __name__ == "__main__":
    main()
