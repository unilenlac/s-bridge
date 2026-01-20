# σ-Bridge
Create a Tradition from a DTS Collection

### Demande :

Dans le cadre du projet ENLAC "Editer numériquement la littérature apocryphe chrétienne", nous utilisons actuellement un programme (https://github.com/unilenlac/xml2stemmarest) qui nous permet de charger des textes (concrètement des transcriptions de manuscrits) au format XML vers un programme complet d’analyse et d'édition critique qui s’appel Stemmaweb (https://github.com/unilenlac/stemmaweb).

Le programme comporte plusieurs faiblesses : 

Il est lancé depuis un ordinateur personnel.
Il utilise des transcriptions de manuscrits qui se trouvent nécessairement stockées sur ordinateur personnel.
Le programme n’accepte que les transcriptions qui mobilisent une DTD précise.
Il n’applique aucune méthode complexe sur la transcription pour la nettoyer, la "neutraliser", la lemmatiser etc, ce qui limite les possibilités de traitement avec Stemmaweb.
Il n'est pas possible d'ajouter une nouvelle transcription une fois le processus de collation ou d'édition critique lancé, sauf à revenir au point de départ. 

Actuellement, les documents se trouvent dans une base de données et il est possible de l'interroger via une interface de programmation (API). Par ailleurs, le programme qui permet de faire les analyses est complet, c'est-à-dire couvre toutes les étapes de l'édition critique, et nous permet maintenant d’exporter des éditions critiques au format XML. Ce dernier possède aussi une interface de programmation (https://github.com/unilenlac/tradition_repo).

Nous souhaitons à présent faire en sorte de lier les deux interfaces via une application intermédiaire. 

La demande est principalement la suivante : **créer une API qui permette à un utilisateur de charger une tradition manuscrite lemmatisée et tokenizée dans Stemmarest via un lien DTS.**

Le programme doit comporter les fonctions suivantes :

- Permettre de récupérer dans une base de données les textes (concrètement des transcriptions de manuscrits) qui doivent être édités critiquement et qui ne se limitent pas à la littérature apocryphe chrétienne. La récupération se fait via un endpoint DTS (https://distributed-text-services.github.io/specifications/).
- Permettre d'appliquer un processus discret de tokenisation, de lemmatisation et d'analyse morpho syntaxique (POS) des transcriptions récupérées.
- Permettre de soumettre des transcriptions ou des extraits de transcriptions à Collatex pour en récupérer une Collation.
- Permettre d'injecter ensuite les transcriptions collationnées dans Stemmarest via son API.
- Idéalement, mettre à jour une tradition via un manuscrit référencé par une API DTS.


#### La demande en détail :

|id| Tâches|Type|Facultatif|Notes|
|---|---|---|---|---|
|1|Étendre l’interface web Stemmaweb avec un composant graphique “importer via DTS"  : le composant permet d'indiquer le lien d'une collection DTS et de définir une série de paramètres pour l'importation.|Module web|Non||
|2|Développer un système σ en charge de récupérer des traditions manuscrites via un lien DTS, de produire des sections (set de versions), de lemmatiser et de tokenizer le contenu des versions, de produire des collations via Collatex et de générer des traditions via Stemmarest.|Backend app / backend feature|Non||
|2.1|Intégrer dans σ un processus de transformation des documents XML en données de type Text|module|non||
|2.2|Intégrer dans σ un pipeline de tâches NLP de base (tokenization, lemmatisation, POS) spécialisées pour le grec ancien (choix libre des algos/modèles). |Module|Non|La chaîne peut mobiliser un LLM en local, si utile/disponible.|
|2.3|Intégrer dans σ la capacité de communiquer avec l’application CollateX pour générer et récupérer des collations.|Module|Non||
|2.4|Intégrer dans σ la capacité de communiquer avec l’API Stemmarest et (directement ou indirectement) pour y importer ou mettre à jour des Collations. |Module|Non||
|2.5|Prévoir dans σ la possibilité de mémoriser des set de versions, de les enrichir avec de nouveaux textes et de mettre à jour les graphs existants sur l’API Stemmarest.|Module|Oui||
|7|Créer une image Docker de σ et fournir la documentation technique nécessaire à son déploiement et à son utilisation.|DevOps / Documentation|Non||

### Stack demandée

- Langage pour σ-Bridge : Python
- Framework web pour σ-Bridge : FastAPI
- Conteneurisation : Docker
- Dépendances NLP : SpaCy ou CLTK (à discuter), possibilité d'utiliser un LLM en local via Ollama
- Autres dépendances : requests, lxml, etc.
- Langage pour le module de l'interface web (Stemmaweb) : Javascript
- portail API: Kong

### Livrables attendus
- Code source complet de σ-Bridge hébergé sur un dépôt GitHub
- Documentation technique détaillée pour l'installation, la configuration et l'utilisation de σ-Bridge
- Image Docker de σ-Bridge prête à être déployée
- Tests unitaires et d'intégration pour assurer la fiabilité et la robustesse de σ-Bridge

### resources utiles
- [DTS Specifications](https://distributed-text-services.github.io/specifications/)
- [DTS API demo (collection endpoint)](https://py-dts-demo.onrender.com/api/dts/v1/collection?id=1-1)
- [Repo Stemmarest (API Tradition Repo)](https://github.com/unilenlac/tradition_repo)
- [Repo Stemmaweb (interface Web)](https://github.com/unilenlac/stemmaweb)
- [Repo xml2stemmarest (ancienne version de σ-Bridge)](https://github.com/unilenlac/xml2stemmarest)
- [CollateX Documentation](https://collatex.net/documentation/)

