"""
i18n.py
───────
Langue de l'extension : celle choisie dans QGIS (Préférences > Options >
Général), fixe pour la session. Le français est la langue du code ; en, es
et pt viennent des dictionnaires i18n/<langue>.json, clés en français.

tr('Texte {0}', valeur) : texte traduit, gabarit rempli. Une clé absente
reste en français (jamais de texte vide).
"""
import json
import os

LANGUES = ('fr', 'en', 'es', 'pt')


# Clé du choix fait dans l'extension (sélecteur de l'en-tête) ; le paquet
# accept a la sienne, comme tous ses réglages.
CLE_LANGUE = ('LizpackPublisherAccept/langue' if (__package__ or '').endswith('_accept')
              else 'LizpackPublisher/langue')


def _langue_qgis():
    try:
        from qgis.PyQt.QtCore import QSettings, QLocale
        s = QSettings()
        choix = str(s.value(CLE_LANGUE, '') or '')
        if choix in LANGUES:
            return choix
        if s.value('locale/overrideFlag', False, type=bool):
            code = s.value('locale/userLocale', '') or ''
        else:
            code = QLocale.system().name()
        code = str(code or '')[:2].lower()
    except Exception:  # hors QGIS (essais)
        code = os.environ.get('LIZPACK_LANGUE', 'fr')[:2].lower()
    if code in LANGUES:
        return code
    return 'en'


LANGUE = _langue_qgis()
_DICO = {}
if LANGUE != 'fr':
    try:
        chemin = os.path.join(os.path.dirname(__file__), 'i18n', LANGUE + '.json')
        with open(chemin, encoding='utf-8') as f:
            _DICO = json.load(f)
    except Exception:
        _DICO = {}


def tr(texte, *args):
    """Traduit `texte` (gabarit à {0}, {1}…) puis le remplit avec args."""
    modele = _DICO.get(texte, texte) if isinstance(texte, str) else texte
    if not args:
        return modele
    try:
        return modele.format(*args)
    except (IndexError, KeyError, ValueError):
        return texte.format(*args)


# ── Messages du serveur ───────────────────────────────────────────────
# Le portail entreprise répond en français ; ses traductions (celles de son
# interface, reprises par extraire_messages_serveur.py) donnent la langue de
# l'extension. Un message composé (« compte inconnu : marie ») est reconnu par
# son format (« compte inconnu : {0} »), comme dans le portail.
import re as _re

_SERVEUR = {}
_MOTIFS = []
if LANGUE != 'fr':
    try:
        with open(os.path.join(os.path.dirname(__file__), 'i18n',
                               'serveur_' + LANGUE + '.json'), encoding='utf-8') as f:
            _SERVEUR = json.load(f)
    except Exception:
        _SERVEUR = {}
    for _fr, _trad in _SERVEUR.items():
        if not _re.search(r'\{\d+\}', _fr):
            continue
        _fixe = _re.sub(r'[^A-Za-zÀ-ÿ]', '', _re.sub(r'\{\d+\}', '', _fr))
        if len(_fixe) < 12:
            continue
        _ordre = []
        _parts = []
        for _p in _re.split(r'(\{\d+\})', _fr):
            _m = _re.fullmatch(r'\{(\d+)\}', _p)
            if _m:
                _ordre.append(int(_m.group(1)))
                _parts.append(r'([\s\S]+?)')
            else:
                _parts.append(_re.escape(_p))
        _MOTIFS.append((_re.compile('^' + ''.join(_parts) + '$'), _ordre, _trad,
                        _fr.split('{')[0]))
    _MOTIFS.sort(key=lambda m: -len(m[3]))


def tr_serveur(texte):
    """Un message reçu du serveur, dans la langue de l'extension s'il est connu."""
    if not _SERVEUR or not isinstance(texte, str) or not texte:
        return texte
    if texte in _SERVEUR:
        return _SERVEUR[texte]
    if texte in _DICO:
        return _DICO[texte]
    for motif, ordre, trad, tete in _MOTIFS:
        if tete and not texte.startswith(tete):
            continue
        m = motif.match(texte)
        if m:
            valeurs = {}
            for i, n in enumerate(ordre):
                valeurs[n] = tr_serveur(m.group(i + 1))
            return _re.sub(r'\{(\d+)\}', lambda x: str(valeurs.get(int(x.group(1)), x.group(0))), trad)
    return texte
