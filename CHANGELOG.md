# Journal des modifications

Les versions suivent [SemVer](https://semver.org/lang/fr/) : `MAJEURE.MINEURE.CORRECTIF`.

---

## 1.1.1 — 2026-09-05

Première version publiable. Trois plantages de QGIS corrigés, un onglet
PostGIS qui diagnostique et répare la base, et le partage d'instances entre
membres d'une équipe.

### Corrections critiques

- **QGIS se fermait brutalement à la connexion d'une instance.**
  `iface.browserModel().reload()` reconstruisait l'arbre de l'explorateur pendant
  que QGIS s'en servait : le processus était abandonné, sans boîte d'erreur ni
  trace. Deux rapports de plantage de QGIS désignaient la même ligne. On
  prévient désormais QGIS par l'API du fournisseur, qui se rafraîchit de
  lui-même.
- **QGIS se fermait aussi en enchaînant deux opérations réseau.**
  Chaque opération rangeait son `QThread` dans un attribut unique et l'écrasait
  à la suivante. Si le premier fil tournait encore, Qt abandonnait le processus
  sur `QThread: Destroyed while thread is still running`. Un second clic sur
  « Se connecter », « Connecter à l'instance » ou « Ouvrir » suffisait.
- **Une fenêtre fantôme survivait au déchargement du plugin.**
  `close()` ne fait que masquer : la fenêtre restait rattachée à QGIS. Chaque
  mise à jour du plugin en laissait une derrière elle, encore connectée.

### Publication et téléchargement

- **La réécriture des connexions PostGIS n'avait jamais fonctionné.** Une
  `AttributeError` dans `rewrite_pg()` était avalée par un `except` muet : tous
  les projets publiés partaient avec leur adresse d'origine au lieu de l'adresse
  interne, et Lizmap ne pouvait pas joindre la base.
- **Ouvrir un projet ne récupérait que les fichiers posés à côté du `.qgs`.**
  Les données rangées dans un sous-dossier restaient introuvables et QGIS
  ouvrait le projet avec ses couches cassées. Le dossier serveur est désormais
  rapatrié en entier.
- **Une seule requête** remplace un aller-retour par fichier, au téléchargement
  comme à la publication.
- Le dossier de destination est demandé, puis retenu.

### Santé de la base — nouveau

Un diagnostic en lecture seule, et des corrections graduées.

- Sept contrôles : index spatial manquant, clef primaire absente ou en `bigint`
  (que QGIS Serveur refuse), statistiques périmées, polygones de plus de
  10 000 sommets, lignes mortes, noms de table bordés d'espaces.
- Trois régimes de correction — **automatique** (index, `ANALYZE`, `VACUUM`),
  **sur confirmation** (clef primaire, conversion de type), **à la main**
  (renommage, `ST_Subdivide`). « Tout optimiser » ne touche jamais à la
  structure.
- Chaque correction appliquée affiche sa commande d'annulation.
- Correction sur la totalité ou sur une sélection.
- Export en CSV ou en script SQL rejouable.
- Les tables de service — schéma `lizmap`, `spatial_ref_sys`, `layer_styles` —
  sont écartées.

### Équipes

- **Instances partagées.** Le contexte d'équipe est transmis au serveur, qui
  vérifie l'adhésion. Un choix « Espace » apparaît dès qu'une équipe existe.
- Les permissions renvoyées par le serveur sont respectées. Sans le droit de
  gestion des fichiers, l'onglet Projets explique la limite au lieu d'afficher
  un arbre vide — le serveur refuse alors jusqu'au simple listage.

### Sécurité

- **Analyse XML durcie.** `defusedxml` s'il est présent, sinon un parseur expat
  refusant les déclarations d'entités : entités externes et bombes d'expansion
  sont bloquées.
- **Le mot de passe va dans le magasin d'authentification de QGIS**, qui le
  chiffre. Jamais en clair dans les réglages.
- **Identifiants SQL cités** à la manière de PostgreSQL : un nom de table forgé
  ne peut pas rompre la citation.
- L'extraction d'archive refuse toute entrée dont le chemin sort du dossier.

### Interface

- Fenêtre à une taille utilisable, mémorisée, centrée sur l'écran du curseur.
- Sections de l'onglet PostGIS redimensionnables.
- Journal repliable, replié par défaut, déployé automatiquement sur erreur.
- Les boutons ne sont actifs que lorsque l'action peut aboutir, et leur
  infobulle nomme ce qui manque : « Ouvrir », « Publier », « Connecter à
  l'instance », « Ajouter à QGIS », « Importer dans PostGIS ».
- Libellé d'onglet tronqué, flèche des listes déroulantes invisible, bandeau
  déformé : corrigés.
- Identifiants mémorisés en option.
- Le dossier choisi devient le répertoire de travail de toutes les boîtes de
  fichiers, et le répertoire de projet de QGIS.

### Qualité

- Bandit : 3 signalements MEDIUM → 0.
- flake8 : 366 → 0, avec une configuration livrée dans le paquet.
- Suppression d'un doublon de classe, de dix imports morts et de code
  inatteignable.

---

## 1.0.0

Version initiale : connexion, navigation, ouverture et publication de projets,
gestion des fichiers, liste des tables PostGIS.
