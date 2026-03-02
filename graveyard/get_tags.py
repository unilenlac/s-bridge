import glob
from bs4 import BeautifulSoup

all_tags = set()
for file in glob.glob("Le Martyre de Philippe - Acta Philippi/*.xml"):
    with open(file, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'xml')
        for tag in soup.find_all(True):
            all_tags.add(tag.name)

print("Unique tags found:")
for t in sorted(all_tags):
    print(f"- {t}")
