# Journal des modifications

Les versions suivent [SemVer](https://semver.org/lang/fr/) : `MAJEURE.MINEURE.CORRECTIF`.

---

## 1.4.0 · 2026-11-09

Quatre langues, et LizPack Entreprise.

- **Quatre langues.** Français, anglais, espagnol et portugais, au choix dans
  l'en-tête ; les messages du serveur et l'export du diagnostic sont traduits.
- **LizPack Entreprise.** Connexion au portail de l'organisation par jeton
  d'API : fichiers, envoi par morceaux, validation, couches PostGIS.
- **Jeton en lecture seule.** La validation reste permise, l'écriture est
  grisée ; elle revient dès qu'un jeton en écriture est utilisé.
- **Projets protégés** ouverts à leur propriétaire et au groupe de mise à jour.
- **Onglet Connexion redessiné** ; le bandeau PostGIS dit la vraie raison.
- **« Corriger dans QGIS »** après une validation.
- **Validation :** les fonds de carte (WMS, XYZ, WMTS, WCS, tuiles
  vectorielles, ArcGIS) ne comptent plus dans le mélange de projections.

---

## 1.3.0 · 2026-10-21

Publier plus vite, et sans échec sur une ligne lente.

- **Directement au serveur de l'instance.** Quand l'instance est servie par
  son serveur, les données y vont sans passer par le central. Les projets
  QGIS passent toujours par LizPack, qui les valide, et partent après leurs
  données.
- **Rien n'est renvoyé pour rien.** Un fichier déjà à jour sur le serveur
  (même taille, copie du serveur plus récente) ne repart pas.
- **Seuls les blocs modifiés.** Un GeoPackage modifie ses pages sur place :
  corriger quelques entités d'un fichier de 300 Mo n'envoie que les blocs de
  4 Mo qui ont changé. Un compactage (VACUUM) réécrit tout le fichier, et
  l'envoi redevient complet cette fois-là.
- **Compressé en route.** GeoPackage, Shapefile, CSV : deux à trois fois
  moins d'octets sur la ligne. Les formats déjà compressés partent tels quels.
- **Reprise.** Une requête perdue se réessaie, et un envoi interrompu (coupure,
  QGIS fermé) reprend là où il s'était arrêté. Chaque bloc est vérifié à
  l'arrivée par son empreinte.
- **Plus de coupure sur les gros envois.** Une publication partait en une
  seule requête, coupée au-delà d'une minute et demie environ : vers le
  central aussi, les envois se font désormais en requêtes courtes.

---

## 1.2.0 — 2026-09-08

Valider un projet avant de le publier, le réparer quand c'est possible, et
retrouver ses couches PostGIS branchées à l'ouverture.

### Valider un projet — nouveau

Un sous-onglet lui est consacré, à côté du gestionnaire de fichiers.

- **Examen par le serveur, sans rien publier.** Le fichier est lu en mémoire
  puis abandonné : rien n'est écrit, rien n'est déposé. Deux entrées — le
  projet actif depuis le bloc de publication, ou un projet déjà en ligne par
  un clic droit dans la liste.
- **Ce qui est contrôlé** : connexions de la base, clefs primaires, index
  spatiaux, projections, cohérence entre le système déclaré et celui de la
  base, expressions, chemins locaux, et coût des mises en page — chaque mise
  en page garnie coûte quelques secondes à la lecture du projet par le
  serveur, et le total se compare à son délai d'abandon.
- **Rapport classé par gravité**, avec conséquence et solution pour chaque
  signalement. Deux règles seules font refuser le dépôt : des couches en
  projections mélangées, et des connexions étrangères à l'instance ; les
  autres dégradent la carte sans l'interdire.

### Reprojection proposée

Un projet dont les couches ne partagent pas le même système de coordonnées
est refusé au dépôt. Le plugin propose de les ramener dans un système unique
**au moment où le refus surviendrait**, plutôt que de renvoyer l'utilisateur
le faire à la main. Le projet est corrigé sur place, sous son propre nom —
c'est lui qu'on rouvrira — et une sauvegarde `<projet>.qgs.bak` est posée à
côté avant toute écriture.

### Ouverture d'un projet

- **Les couches PostGIS se rebranchent seules.** Un projet publié porte
  l'adresse interne de la base, celle que Lizmap emploie depuis le serveur :
  ouvert tel quel sur un poste de travail, il arrivait avec toutes ses couches
  muettes. Le plugin repose l'adresse du poste et confie le mot de passe au
  magasin d'authentification de QGIS — il n'est jamais écrit en clair dans le
  projet enregistré sur le disque. Seules les couches qui pointent vers la base
  de l'instance sont touchées.

### Publication

- **Le tableau de bord voyage avec son projet.** Un `.qdash` posé à côté du
  `.qgs` part dans le même envoi : sans lui, le tableau de bord en ligne
  restait figé sur son ancienne définition, sans que rien ne le signale.
- **La destination suit le dossier ouvert.** Elle était suggérée une seule
  fois, à l'ouverture du projet, et valait la racine : descendre dans un
  dossier n'y changeait rien, et le projet y repartait quand même. Un fichier
  choisi d'un clic reste prioritaire, jusqu'au changement de dossier.

### Connexion

- **Bouton Rafraîchir** : redemande au serveur tout ce qui est lu à la
  connexion — identifiants de la base, quota, permissions, fichiers — sans
  changer d'instance ni se déconnecter.
- **La déconnexion retire les connexions PostgreSQL** posées par le plugin, y
  compris celles laissées par une session précédente, dont le mot de passe
  pouvait avoir changé entre-temps.

### Interface

- L'onglet Projets se divise en **Gestionnaire de fichiers** et **Valider un
  projet** : gérer des fichiers et lire un rapport se disputaient la hauteur.
- Les dossiers affichent leur **nombre d'éléments** — un dossier n'a pas de
  taille propre, et la calculer voudrait dire parcourir tout son contenu à
  chaque affichage ; le serveur, lui, les compte déjà en listant.
- La colonne **Modifié** porte l'heure autant que la date.
- Le **journal** se copie d'un bouton, s'ouvre toujours replié, se referme
  d'un clic ailleurs, et ne se déplie plus par-dessus un rapport qui montre
  déjà tout.
- La **version** du plugin s'affiche dans le bandeau, lue dans `metadata.txt`.

### Corrections

- **« Charger les tables » gelait QGIS.** La connexion à la base et la
  requête tournaient dans le fil de l'interface : jusqu'à dix secondes sans
  réponse, Windows déclarait l'application bloquée et proposait de la fermer.
- **La connexion PostgreSQL enregistrée ne pouvait pas réutiliser son mot de
  passe.** L'API du fournisseur réécrit le groupe de réglages à partir de
  l'URI et perdait les deux drapeaux d'enregistrement, écrits avant elle ;
  l'explorateur affichait « La connexion a échoué ».
- **Une fenêtre réduite ne revenait pas** au clic sur l'icône : pour Qt elle
  reste « visible », et `show()` ne la restaure pas.
- **Les onglets écrasaient leur contenu** sur une fenêtre courte — boutons à
  cheval, champs coupés en deux, arbre réduit à une ligne. Connexion et
  Projets défilent désormais, et les libellés d'onglets ne sont plus rognés.
- **Le rapport ne tronque plus rien** : le constat se replie sur plusieurs
  lignes, la sélection porte sur la ligne entière.
- **Les listes déroulantes n'ont plus deux bordures** emboîtées.
- **Un message d'erreur technique** — « Méthode POST non autorisée » — est
  remplacé par une phrase utile : la fonctionnalité n'est pas encore
  disponible sur ce serveur. Le détail part dans le journal de QGIS, à l'usage
  du support.

### Interne

- Le **diagnostic de la base** n'a plus qu'une implémentation, côté serveur :
  deux copies du même contrôle finissent toujours par diverger.
- Le plugin se fabrique en **deux paquets installables côte à côte**,
  production et recette, par `generer_paquets.py` — dossier, menu, réglages et
  connexions distincts, pour tester les deux environnements sans qu'ils se
  marchent dessus.

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
