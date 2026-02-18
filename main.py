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

    # url: str = "https://dts.perseids.org/documents"
    # params: str = {
    #     "id": "urn:cts:greekLit:tlg0012.tlg001.perseus-grc2",
    #     "start": "1.1",
    #     "end": "1.9"
    # }

def main():
    url: str = "http://ftsr-dev.unil.ch:8000/api/dts/v1/document"
    params: str = {"resource": "athous-iviron-450"}
    headers: str = {"accept": "application/xml"}
    response: str = requests.get(url, params=params, headers=headers)

    text_to_process: str = response.text

    # print(text_to_process)

    # Use the 'xml' parser specifically for TEI
    soup : bs4.BeautifulSoup = BeautifulSoup(text_to_process, features="xml")
    # print(soup.body.prettify())
    nlp = NLP("grc", backend="stanza", suppress_banner=True)

    # greek_text = soup.body.get_text(separator=" ", strip=True)
    # doc = nlp.analyze(greek_text)
    test_punct = nlp.analyze("ὁ δὲ, φίλιππος εἶπεν·")

    # for word in doc.words:
    #     print(f"Token: {word.string:<15} | Lemma: {word.lemma:<15} | POS: {word.upos} | IDSEN : {word.index_sentence}")
    for word in test_punct.words:
        print(f"Token: {word.string:<15} | Lemma: {word.lemma:<15} | POS: {word.upos} | IDSEN : {word.index_sentence}")


if __name__ == "__main__":
    main()
