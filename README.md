# LIZPACK Publisher — Plugin QGIS

Gérer les projets et les données d'une instance LIZPACK sans quitter QGIS :
parcourir les fichiers, ouvrir un projet avec toutes ses données, publier vers
Lizmap, et diagnostiquer la base PostGIS.

---

## Fonctionnalités

### Connexion

- **Authentification JWT** (email + mot de passe), puis choix de l'instance.
- **Identifiants mémorisés** en option. L'email va dans les réglages QGIS, le
  mot de passe dans le **magasin d'authentification** de QGIS, qui le chiffre.
  Il n'est jamais écrit en clair.
- **Espaces partagés** : si une équipe vous a partagé ses instances, un choix
  « Espace » apparaît. Le plugin transmet le contexte au serveur, qui vérifie
  l'adhésion et décide. Sans le droit de gestion des fichiers, l'onglet Projets
  affiche la raison au lieu d'un arbre vide.

### Projets

- **Ouvrir un projet `.qgs`/`.qgz`** avec l'intégralité de son dossier serveur,
  sous-dossiers compris — le serveur assemble une archive, une seule requête.
- **Destination au choix**, mémorisée d'une fois sur l'autre.
- **Publier** le projet QGIS actif. Les connexions PostGIS du `.qgs` sont
  réécrites vers l'adresse interne de l'instance, le `.qgs.cfg` et les données
  locales référencées partent dans le même envoi.
- Créer, envoyer, renommer, supprimer, copier, déplacer.

### PostGIS

- **Lister les tables** et les ajouter comme couches. La connexion est
  enregistrée dans QGIS automatiquement.
- **Importer** une couche QGIS vers la base de l'instance.
- **Diagnostiquer la base** — analyse en lecture seule qui relève :
  - colonne géométrique sans index GIST ;
  - table sans clef primaire entière, avec recherche d'une colonne existante
    réutilisable plutôt qu'une colonne ajoutée ;
  - clef primaire en `bigint`, que QGIS Serveur refuse ;
  - statistiques absentes ou périmées ;
  - polygones de plus de 10 000 sommets ;
  - lignes mortes accumulées ;
  - noms de table bordés d'espaces.

  Les tables de service — schéma `lizmap`, `spatial_ref_sys`, `layer_styles` —
  sont écartées.

- **Optimiser**, sur la totalité ou sur une sélection. Trois régimes :

  | Correction | Comportement |
  |---|---|
  | Automatique | index, `ANALYZE`, `VACUUM` — réversible, appliqué par « Tout optimiser » |
  | Sur confirmation | clef primaire, conversion de type — jamais par « Tout optimiser » |
  | À la main | renommage, `ST_Subdivide` — le SQL est donné, jamais exécuté |

  Chaque correction appliquée affiche sa commande d'annulation dans le journal.

- **Exporter** le diagnostic en CSV (rapport) ou en SQL (script rejouable, les
  corrections manuelles commentées).

### Interface

- Fenêtre redimensionnable, taille et position retenues.
- Sections de l'onglet PostGIS séparées par des poignées mobiles.
- Journal repliable, déployé automatiquement en cas d'erreur.

---

## Installation

### Copier le plugin dans QGIS

**Windows** — double-cliquer sur `install_plugin.bat`.

**Manuellement** — copier le dossier `lizpack_publisher/` dans :

```
%APPDATA%\QGIS\QGIS3\profiles\<profil>\python\plugins\
```

### Activer

Extensions → Gérer les extensions → **LizPack Publisher** → cocher.

L'entrée apparaît alors dans **Internet ▸ LizPack ▸ LizPack Publisher**
— « Internet » est le nom français du menu *Web*.

---

## Changer d'environnement

Le serveur interrogé est fixé par une constante dans
`lizpack_publisher/api_client.py` :

```python
# ACCEPT : https://acceptapi.lizpack.com
# PROD   : https://api.lizpack.com
API_BASE = 'https://api.lizpack.com'
```

L'adresse de la documentation, elle, est dans `dialog.py`, méthode `_tab_docs()` :

```python
_SUPPORT_URL = 'https://lizpack.com/client/aide-support'
```

Les deux doivent être changées ensemble.

---

## Structure

```
plugin/
├── lizpack_publisher/
│   ├── __init__.py        — fabrique QGIS
│   ├── plugin.py          — point d'entrée, menu et barre d'outils
│   ├── dialog.py          — interface, cinq onglets
│   ├── api_client.py      — client HTTP de l'API (contient API_BASE)
│   ├── workers.py         — QThreads non bloquants
│   ├── optimisation.py    — diagnostic et corrections PostGIS
│   ├── journal.py         — trace les erreurs sans gravité
│   ├── icon.png / icon.svg
│   └── metadata.txt
├── .flake8                 — configuration du linter, hors du paquet
└── install_plugin.bat
```

Le fichier `.flake8` doit rester **hors** de `lizpack_publisher/`. Le
validateur du dépôt QGIS signale toute configuration d'outil livrée avec un
plugin et déclasse la validation en « Validated (configured) », un
administrateur devant alors vérifier à la main quelles règles ont été
assouplies. Il ne s'agit ici que de mise en forme — longueur de ligne et
alignement — ce qui ne justifie pas de faire douter de l'analyse de sécurité.

---

## Dépendances

| Bibliothèque | Fournie avec QGIS | Usage |
|---|---|---|
| `http.client`, `zipfile`, `csv` | oui (stdlib) | API, archives, export |
| `xml.etree` + `xml.parsers.expat` | oui (stdlib) | lecture des `.qgs` |
| `PyQt5` | oui | interface |
| `psycopg2` | **généralement** | onglet PostGIS et diagnostic |

`psycopg2` accompagne la plupart des installations QGIS. En son absence, la
liste des tables passe par le fournisseur QGIS, mais **le diagnostic de la base
n'est pas disponible** et le dit.

Le plugin n'installe aucun paquet et n'en réclame aucun.

---

## Notes techniques

**Analyse XML.** Les `.qgs` sont lus par `parse_qgs_xml()`, qui utilise
`defusedxml` s'il est présent et sinon un parseur expat durci : les
déclarations d'entités sont refusées, ce qui bloque les entités externes et les
bombes d'expansion. La DOCTYPE reste acceptée — QGIS en écrit une dans chaque
projet.

**Fils d'exécution.** Chaque opération réseau tourne dans un `QThread` suivi par
`_suivre()`. Sans cette référence, un fil écrasé en pleine course était détruit
par Python et Qt abandonnait le processus : QGIS se fermait sans trace. À la
fermeture de la fenêtre, les fils encore actifs sont débranchés et confiés au
module plutôt que détruits.

**Identifiants SQL.** Tout nom venant du catalogue passe par `citer()`, qui
double les guillemets internes. Un nom de table forgé ne peut pas rompre la
citation.

---

## Licence

GNU General Public License v3.0 ou ultérieure — voir [LICENSE](LICENSE).

Ce choix n'est pas discrétionnaire : un plugin QGIS importe `qgis.core`,
`qgis.gui` et PyQt5, tous sous GPL. Distribué publiquement, il constitue une
œuvre dérivée et doit porter une licence compatible. La GPL interdit d'ajouter
une restriction d'usage — « non commercial » notamment — ce qui rend ce type de
clause impossible ici.

En pratique, la GPL protège le travail : quiconque redistribue le plugin, même
contre paiement, doit en fournir le code source sous la même licence. Personne
ne peut le refermer.
