# Revue et Évolution de l'Architecture (s-bridge)

Ce document résume les initiatives architecturales introduites récemment dans la branche de développement et propose quelques ajustements techniques pour garantir la stabilité en production. 

L'objectif de ces modifications est de consolider et de pérenniser les idées;
    1.réutilisation des connexions HTTP, 
    2.mise en place du pattern Preparator, 
    3.transition vers une approche agnostique
tout en résolvant certains conflits profonds liés au cycle de vie asynchrone de FastAPI.

---

## 1. Gestion des Connexions HTTP (Connection Pooling)

**L'idée :**
L'initiative de découpler `httpx.AsyncClient` des classes clientes (`DTSClient`, `CollatexClient`, `StemmarestClient`) pour le passer par injection de dépendance est une excellente pratique. Cela permet de réutiliser les connexions HTTP globales du serveur et d'éviter l'épuisement des sockets (socket exhaustion) lors d'un grand nombre de requêtes.

**L'évolution technique :**
Nous avons "passé à l'échelle" cette idée en créant un véritable pool de connexions global et persistant. Au lieu d'utiliser une dépendance FastAPI (`Depends(http_client)`) qui instancie et détruit le client à chaque requête HTTP, nous instancions le `httpx.AsyncClient` une seule fois dans le gestionnaire `lifespan` de `main.py` et l'attachons à `app.state.http_client`. Les clients l'utilisent ensuite de manière partagée.

**Pourquoi cet ajustement était nécessaire :**
Dans FastAPI, une dépendance (comme la fonction `http_client` contenant un `yield`) est strictement liée au cycle de vie de la requête HTTP entrante. Lorsqu'on passe ce client HTTP à une tâche d'arrière-plan (`BackgroundTasks` lançant `run_collate_job`), FastAPI ferme automatiquement la connexion dès que la réponse HTTP initiale est renvoyée à l'utilisateur. Au moment où le *worker* d'arrière-plan commence véritablement à travailler, le client est déjà fermé, ce qui provoque inévitablement l'erreur critique `RuntimeError: Event loop is closed`. 
En utilisant le pool global persistant sur `app.state`, le background worker peut désormais accomplir de longues tâches de collation en toute sécurité.

---

## 2. Le Pattern "Preparator" et la Sérialisation

**L'idée :**
L'extraction de la logique spécifique à DTS dans `services/preparators.py` (`DtsPreparator`) est une implémentation très élégante de la Séparation des Préoccupations (Separation of Concerns). Cela standardise la façon dont les collections sources sont prétraitées, indépendamment du serveur d'origine.

**L'évolution technique :**
Nous avons remplacé l'utilisation de `pickle` par `json` pour la sauvegarde temporaire des données de collation sur le disque, et restauré l'extension `.json`.

**Pourquoi cet ajustement était nécessaire :**
L'utilisation de `pickle` est très performante pour des objets Python purement internes et de confiance. Cependant, elle présente une faille de sécurité critique lorsqu'elle est utilisée pour désérialiser des données provenant d'APIs externes non vérifiées (elle permet l'exécution de code arbitraire si le payload est altéré). De plus, contrairement à l'intuition, `pickle.load()` charge l'intégralité de l'arbre de données en mémoire exactement comme `json.load()`, il n'y a donc pas de gain "overhead" pour la mémoire vive dans ce contexte. Le format `json` garantit la sécurité absolue et la portabilité des données temporaires entre les services.

---

## 3. Approche Agnostique et Schéma de Base de Données

**L idée :**
Le commentaire "TODO" soulignant la redondance de `dts_base_url` par rapport à `collection_url` était tout à fait exact. Pour supporter d'autres sources que l'écosystème DTS à l'avenir, il fallait se détacher de la nomenclature spécifique "DTS" dans nos schémas de base de données.

**L'évolution technique :**
La migration Alembic est générée pour supprimer les champs `dts_base_url` et `collection_id` du modèle `Job` (en gardant uniquement son UUID et `collection_url`) et remplacé `dts_base_url` par `collection_url` dans le modèle `Tradition`. Le processus de nettoyage lors d'un `cancel_job` utilise désormais l'URL pour récupérer dynamiquement le nom de la collection.

**Pourquoi cet ajustement était nécessaire :**
Cela rend l'architecture de `s-bridge` complètement agnostique. Le modèle `Job` ne dépend plus d'une structure DTS stricte, préparant le terrain pour l'intégration de n'importe quelle autre source de données externe de manière transparente.

---

## 4. Exécution des TODOs restants

Pour finaliser la vision du code, la base est également nettoyée en traitant les TODOs explicites :

*   **Centralisation du Logging :** Comme suggéré dans les commentaires de `main.py`, la configuration du logger a été extraite dans un nouveau module dédié `core/logging.py`. Cela rend le point d'entrée de l'application beaucoup plus lisible et pose une base scalable pour de futurs *file handlers*.
*   **Gestion des Exceptions :** Les commentaires vides `# todo : handle correctly the Exceptions` présents dans `helpers/helpers.py` ont été remplacés par des blocs `try/except` stricts et explicites, ciblant spécifiquement `httpx.HTTPStatusError` et `httpx.RequestError`. Cela garantit que le serveur ne plantera pas silencieusement et remontera des logs précis en cas de timeout réseau.

---

## 5. Le Pattern Client (Défense de DTSClient)

La décision de déprécier `DTSClient` pour éparpiller des appels `httpx.get` bruts dans `helpers.py` et `DtsPreparator` contourne certains principes fondamentaux d'ingénierie logicielle. Le pattern Client existe précisément pour abstraire la complexité des interactions réseau externes du cœur de la logique métier.

Voici les arguments architecturaux en faveur du maintien de la classe `DTSClient` :

*   **Encapsulation et Séparation des Préoccupations :**
    La logique métier (`WitnessService` ou `DtsPreparator`) ne devrait jamais avoir à se soucier de *comment* parler à un serveur externe. Sans le Client, `DtsPreparator` se retrouve à gérer des paramètres spécifiques à l'API comme `down=1`, `limit=100`, et des boucles `while` pour la pagination. Le Client masque tout cela : le service appelle simplement une méthode de haut niveau et obtient une liste propre. Si l'API cible change sa stratégie de pagination demain, seul le Client doit être mis à jour.
*   **Testabilité et Mocking :**
    Avec des appels HTTP dispersés directement dans la logique métier, tester unitairement le pipeline NLP nécessite soit une connexion réseau active, soit des mocks HTTP complexes et fragiles. Une classe Client dédiée est triviale à mocker (ex: substituer une méthode pour renvoyer du faux XML), ce qui permet de tester la logique métier en isolation totale avec fiabilité et rapidité.
*   **Gestion Centralisée des Erreurs :**
    Le Client agit comme une couche anti-corruption (Anti-Corruption Layer). Si le serveur externe renvoie un payload d'erreur spécifique, le Client le capture, le logge de manière centralisée, et le traduit en une exception métier standard. Il est très risqué de laisser des processus d'arrière-plan crasher parce qu'ils ne savent pas analyser une réponse HTTP inattendue au milieu d'un fichier utilitaire.
*   **Respect des Contrats (Approche Agnostique) :**
    L'approche réellement agnostique repose sur le polymorphisme. En définissant une interface de base, `DTSClient` l'implémente. Si nous ajoutons demain un client pour un autre protocole, il implémentera la même interface. La logique métier reçoit un "Client" abstrait et ignore les spécificités du serveur interrogé. Des fonctions utilitaires éparses (comme `get_xml_from_dts_url()`) créent au contraire un couplage fort avec l'écosystème spécifique.
*   **Gestion de l'État et Cache :**
    Les fonctions utilitaires sont sans état (stateless). Chaque appel nécessite potentiellement une nouvelle requête réseau. Un objet Client peut maintenir un état en mémoire (comme c'était le cas avec `self._collection_cache` dans le `DTSClient` d'origine), évitant ainsi de répéter des requêtes HTTP identiques lors de la même opération. En détruisant la classe Client, on perd cette capacité native de mise en cache élégante.
