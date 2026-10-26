# Dictée locale — Design du popup d'enregistrement

Document de design et de spécification — version 1.0 Projet : app de dictée vocale Windows avec Whisper local (PySide6)

---

## 1. Vision et principes

Le popup est la seule partie visible de l'app. Il apparaît quelques secondes, plusieurs dizaines de fois par jour. Il doit donc être **beau sans jamais déranger**.

**Objectif en une phrase :** une pastille de verre sombre, large et fine, qui flotte discrètement en bas de l'écran et dont les ondes sonores respirent avec ta voix.

**Cinq principes**

1. **Discret** : faible contraste avec le bureau, aucune couleur criarde, aucun clignotement agressif. On le sent, on ne le subit pas.
2. **Lisible en un coup d'œil** : en moins d'une demi-seconde, on sait si l'app écoute, réfléchit ou a terminé.
3. **Vivant** : les waveforms réagissent réellement au niveau du micro. Si la voix monte, les barres montent. Ça rassure : « il m'entend ».
4. **Jamais intrusif** : le popup ne vole jamais le focus du champ texte actif, ne capte pas la souris et ne masque pas le contenu important.
5. **Cohérent avec Windows 11** : coins arrondis, matériau translucide, police système, mouvement doux.

---

## 2. Anatomie et dimensions

### 2.1 Taille

| Élément | Valeur (pixels logiques) |
| --- | --- |
| Largeur | 420 px |
| Hauteur | 84 px |
| Rayon des coins | 42 px (pilule complète) |
| Marge d'ombre (zone transparente autour) | 24 px de chaque côté |
| Fenêtre réelle (avec marge d'ombre) | 468 × 132 px |

Le popup est « un peu large » comme demandé : 420 px est environ trois fois la hauteur, ce qui donne une vraie pilule horizontale sans occuper trop d'écran.

### 2.2 Position

- **Par défaut** : centré horizontalement, à **56 px au-dessus du bord bas de la zone de travail** (au-dessus de la barre des tâches).
- **Écran** : celui qui contient le curseur de la souris ou la fenêtre active au moment où tu appuies sur le raccourci. Utiliser `QGuiApplication.screenAt(QCursor.pos())`.
- **Options** (dans les réglages) : bas-centre, haut-centre, bas-droite, ou position libre mémorisée.
- **DPI** : toutes les valeurs ci-dessus sont logiques. Qt gère l'échelle 125 %, 150 % ou 200 % automatiquement, à condition de ne jamais coder de pixels physiques.

### 2.3 Découpage interne (de gauche à droite)

```
┌──────────────────────────────────────────────────────────┐
│  ●   ▂▃▅▇▅▃▂▁▂▄▆▇▆▄▂▁▂▃▅▃▂▁   00:07        FR  │
│  ↑            ↑                    ↑         ↑          │
│ indicateur  waveforms            chrono    langue       │
└──────────────────────────────────────────────────────────┘
```

| Zone | Largeur | Contenu |
| --- | --- | --- |
| Gauche | 64 px | Pastille d'état (cercle 12 px dans un halo de 28 px) |
| Centre | environ 250 px | Waveforms (32 barres) |
| Droite | 106 px | Chrono + puce de langue |

Padding intérieur horizontal : 24 px. Les zones sont séparées par des espaces, jamais par des traits.

---

## 3. Matériau et style visuel

### 3.1 Concept : « verre fumé »

Une pilule sombre, légèrement translucide, avec un très fin liseré clair. Pas de dégradé fort sur le fond : toute la couleur est réservée aux waveforms.

### 3.2 Palette (thème sombre, par défaut)

| Rôle | Valeur | Usage |
| --- | --- | --- |
| Fond | `rgba(22, 24, 29, 0.86)` | Corps de la pilule |
| Fond (repli sans flou) | `#16181D` | Si l'acrylique n'est pas disponible |
| Liseré | `rgba(255, 255, 255, 0.09)` | Bordure intérieure de 1 px |
| Reflet haut | `rgba(255, 255, 255, 0.05)` | Dégradé de 1 px en haut, effet de verre |
| Texte principal | `#E8EAF0` | Chrono |
| Texte secondaire | `#8B90A0` | Langue, indications |
| Accent A (départ des barres) | `#8B9BFF` | Bleu-violet doux |
| Accent B (fin des barres) | `#5EEAD4` | Turquoise doux |
| Enregistrement | `#FF6B7A` | Pastille d'état « écoute » |
| Succès | `#4ADE80` | Pastille et coche |
| Erreur | `#F87171` | Pastille et croix |
| Attention | `#FBBF24` | Audio trop court, micro muet |

Les barres utilisent un **dégradé horizontal** de l'accent A (côté gauche) vers l'accent B (côté droit). Ce dégradé est calculé une seule fois pour toute la zone, pas barre par barre, pour que l'ensemble ressemble à une seule onde colorée.

### 3.3 Thème clair (optionnel)

Suivre le thème de Windows (`QStyleHints.colorScheme()`).

| Rôle | Valeur |
| --- | --- |
| Fond | `rgba(250, 250, 252, 0.88)` |
| Liseré | `rgba(0, 0, 0, 0.08)` |
| Texte principal | `#1B1D24` |
| Texte secondaire | `#6B7080` |
| Accent A / B | `#5B6CF0` / `#14B8A6` |

### 3.4 Flou et ombre

- **Flou d'arrière-plan** : appliquer l'acrylique Windows 11 via `DwmSetWindowAttribute` (`DWMWA_SYSTEMBACKDROP_TYPE` = 3, « transient window »). Si indisponible (Windows 10), repli sur le fond opaque `#16181D`.
- **Ombre portée** : une couche douce dessinée dans la marge de 24 px : décalage vertical 8 px, flou 28 px, couleur `rgba(0, 0, 0, 0.35)`.
- Ne jamais empiler plusieurs ombres : l'ensemble doit rester léger.

### 3.5 Typographie

- Famille : **Segoe UI Variable** (repli : Segoe UI).
- Chrono : 15 px, graisse semi-bold, **chiffres tabulaires** (`font-feature-settings: tnum`) pour que le texte ne « danse » pas quand les secondes changent.
- Puce de langue : 11 px, graisse medium, majuscules, espacement de lettres +0,06 em.
- Texte d'état (transcription, erreurs) : 13 px, regular.

---

## 4. Les états du popup

Le popup est une petite machine à états. Chaque état a son apparence et sa durée.

### 4.1 Tableau récapitulatif

| État | Déclencheur | Pastille | Centre | Droite | Durée |
| --- | --- | --- | --- | --- | --- |
| Caché | Repos | — | — | — | — |
| Écoute | Raccourci enfoncé | Rouge, pulsation lente | Waveforms réactives | Chrono + « FR » | Tant que la touche est tenue |
| Transcription | Touche relâchée | Bleu-violet, rotation | Vague « shimmer » | « Transcription… » | Environ 0,3 à 2 s |
| Succès | Texte collé | Verte, coche | Barres qui s'aplatissent | « Collé » | 600 ms puis disparition |
| Trop court | Audio inférieur à 0,4 s | Ambre | Ligne plate | « Trop court » | 900 ms |
| Aucun son | Niveau quasi nul | Ambre | Ligne plate | « Aucun son détecté » | 1,2 s |
| Erreur | Exception | Rouge, croix | Ligne plate | Message court | 1,8 s |
| Chargement | Démarrage de l'app | Gris | Barres qui s'allument une à une | « Chargement du modèle » | Jusqu'à « prêt » |

### 4.2 État « Écoute » (le plus important)

- La pastille de gauche est un cercle rouge doux de 12 px, entouré d'un halo qui pulse (voir 6.3).
- Les 32 barres réagissent au niveau du micro (voir section 5).
- Le chrono démarre à `00:00` et s'incrémente chaque seconde. Au-delà de 60 s, il passe au format `1:05`.
- Une fine indication « Relâchez pour coller » peut apparaître sous le chrono pendant les 2 premières secondes seulement, puis s'efface. Ça aide au début sans fatiguer ensuite (réglable).

### 4.3 État « Transcription »

- La pastille devient bleu-violet et fait une rotation lente (arc de cercle de 270°, 1 tour par seconde).
- Les barres cessent de réagir au micro. À la place, une **vague lumineuse** parcourt l'ensemble de gauche à droite (effet « shimmer », 1,2 s par passage), sur des barres ramenées à une hauteur basse et régulière.
- Avec ta RTX 5070 Ti, cet état durera souvent moins d'une seconde. Il ne doit donc jamais clignoter : ne l'afficher qu'après un **délai de 120 ms**. Si la transcription se termine avant, on passe directement à « Succès ».

### 4.4 État « Succès »

- La pastille devient verte et une coche se dessine (trait animé en 200 ms).
- Les barres redescendent à plat en 180 ms.
- Le popup reste 600 ms, puis disparaît.
- Option : mode « silencieux total » où le popup disparaît immédiatement sans passer par l'état Succès.

### 4.5 États d'avertissement et d'erreur

- Même structure que « Succès » mais avec la couleur concernée et un message de 2 à 4 mots maximum.
- Pas de bouton, pas de fenêtre modale : le popup s'en va tout seul.
- Les détails techniques d'une erreur vont dans un fichier journal, jamais dans le popup.

---

## 5. Les waveforms (cœur du design)

### 5.1 Géométrie

| Paramètre | Valeur |
| --- | --- |
| Nombre de barres | 32 |
| Largeur d'une barre | 4 px |
| Espace entre barres | 4 px |
| Largeur totale | 32 × 4 + 31 × 4 = 252 px |
| Hauteur minimale | 4 px (une simple pastille, jamais un trait invisible) |
| Hauteur maximale | 44 px |
| Extrémités | Complètement arrondies (rayon = moitié de la largeur) |
| Alignement | Symétrique par rapport à l'axe horizontal central |

Les barres sont dessinées symétriquement vers le haut et vers le bas depuis le centre. C'est ce qui donne l'aspect « onde sonore » classique et élégant.

### 5.2 D'où viennent les données

1. Le flux audio du micro est lu par `sounddevice` par blocs de 20 à 30 ms.
2. Pour chaque bloc, on calcule le **niveau RMS**, converti en échelle perceptive (voir ci-dessous).
3. Ce niveau est envoyé à l'interface via un **signal Qt** (jamais en appelant l'interface directement depuis le thread audio).
4. L'interface met à jour les barres à **60 images par seconde** avec un `QTimer` de 16 ms.

**Conversion en échelle perceptive**

```python
import numpy as np

def niveau(bloc):
    rms = float(np.sqrt(np.mean(bloc ** 2)))
    db = 20 * np.log10(max(rms, 1e-6))        # de -120 à 0 dB
    # on garde la plage utile de la voix : -55 dB (silence) à -12 dB (fort)
    return min(1.0, max(0.0, (db + 55) / 43))
```

Cette plage rend les barres expressives même pour une voix normale avec le micro d'un portable, où le niveau brut reste faible (ton test indiquait 0,101).

### 5.3 Du niveau aux 32 barres

On ne dessine pas 32 mesures différentes (le micro ne donne qu'un niveau global). On fabrique l'effet ainsi :

1. Garder un **historique glissant** des 32 derniers niveaux : à chaque nouvelle mesure, la nouvelle valeur entre au centre et les anciennes s'écartent vers les bords (l'onde « sort » du centre), ou entre à droite et défile vers la gauche. Le défilement depuis le centre est plus élégant avec une pilule symétrique.
2. Multiplier chaque barre par une **enveloppe en cloche** : les barres du centre atteignent 100 % de la hauteur maximale, celles des bords 35 %. Ça donne une silhouette d'oeil ou de fuseau.
3. Ajouter une **micro-variation par barre** (±8 %) fixe, tirée au hasard une fois au démarrage, pour casser la régularité.
4. Appliquer le lissage (5.4).

```python
enveloppe = [0.35 + 0.65 * np.exp(-((i - 15.5) / 9.0) ** 2) for i in range(32)]
```

### 5.4 Lissage et physique (ce qui rend le mouvement « beau »)

Une barre qui suit directement le signal paraît nerveuse et saccadée. On applique un lissage **asymétrique** :

- **Montée rapide** (attaque) : coefficient 0,55 par image, pour réagir instantanément à une syllabe.
- **Descente lente** (relâchement) : coefficient 0,12 par image, pour que les barres retombent avec douceur.

```python
for i in range(32):
    cible = historique[i] * enveloppe[i] * variation[i]
    k = 0.55 if cible > hauteur[i] else 0.12
    hauteur[i] += (cible - hauteur[i]) * k
```

En plus : si le niveau est inférieur à 0,04 (silence), les barres ne s'aplatissent pas complètement mais respirent (voir 5.5).

### 5.5 Mode « respiration » (silence)

Quand tu appuies sur le raccourci mais ne parles pas encore, les barres ne doivent pas être mortes. Elles ondulent doucement :

```python
hauteur_repos[i] = 0.06 + 0.04 * sin(t * 1.6 + i * 0.35)
```

Amplitude très faible (6 à 10 % de la hauteur max), période d'environ 4 secondes. Dès que la voix arrive, les barres réelles prennent le dessus avec la montée rapide.

### 5.6 Rendu

- `QPainter` avec `Antialiasing` activé.
- Chaque barre : `drawRoundedRect` avec un rayon de 2 px.
- Le dégradé horizontal (accent A vers accent B) est un `QLinearGradient` défini sur toute la largeur de la zone.
- **Halo discret** : redessiner les mêmes barres une première fois avec une opacité de 18 % et une largeur de 8 px pour simuler une lueur. À limiter aux barres les plus hautes, pour garder de bonnes performances.
- Opacité globale des barres : 92 % pour rester posé sur le fond sombre.

---

## 6. Mouvement et animations

### 6.1 Principes

- Rien ne bouge plus de **250 ms** sauf les waveforms, les boucles d'attente et la pulsation.
- Les courbes sont toujours **douces à la sortie** (ease-out) pour l'apparition et **douces à l'entrée** (ease-in) pour la disparition.
- Pas de rebond ni d'effet « cartoon ».

### 6.2 Apparition et disparition

| Animation | Durée | Courbe | Détails |
| --- | --- | --- | --- |
| Apparition | 180 ms | `cubic-bezier(0.16, 1, 0.3, 1)` (OutExpo/OutQuint) | Opacité 0 → 1, translation de +10 px vers le haut, échelle 0,96 → 1 |
| Disparition | 140 ms | `cubic-bezier(0.4, 0, 1, 1)` (ease-in) | Opacité 1 → 0, translation de −6 px, échelle 1 → 0,98 |
| Changement d'état | 160 ms | ease-in-out | Fondu enchaîné de la couleur de la pastille et du texte de droite |

En Qt : `QPropertyAnimation` sur `windowOpacity` et sur `pos`, regroupées dans un `QParallelAnimationGroup`.

### 6.3 Pulsation de la pastille d'écoute

- Le halo autour du point rouge grandit de 14 px à 28 px de diamètre et s'efface (opacité 35 % → 0 %) sur **1,6 seconde**, en boucle.
- Le point central lui-même ne bouge pas. Seul le halo respire.

### 6.4 Chrono

- Les chiffres changent sans animation (pas de défilement), ce qui évite l'agitation visuelle.
- Option : le chrono passe en ambre au-delà de 60 secondes pour suggérer une dictée longue.

### 6.5 Accessibilité du mouvement

Si Windows a l'option « Effets d'animation » désactivée, ou si l'utilisateur coche « Réduire les animations » dans les réglages :

- Apparition et disparition : simple fondu de 100 ms, sans translation ni échelle.
- Waveforms : conservées (elles portent l'information), mais sans halo ni respiration.
- Pastille : pas de pulsation, couleur fixe.

---

## 7. Comportement de la fenêtre (critique pour une dictée)

Le popup ne doit **jamais** prendre le focus : sinon, le collage du texte partirait dans le popup au lieu du champ actif.

### 7.1 Attributs Qt

```python
self.setWindowFlags(
    Qt.WindowType.FramelessWindowHint
    | Qt.WindowType.WindowStaysOnTopHint
    | Qt.WindowType.Tool
    | Qt.WindowType.WindowDoesNotAcceptFocus
)
self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)  # clics traversants
```

### 7.2 Styles Windows complémentaires (via ctypes)

Ajouter les styles étendus `WS_EX_NOACTIVATE`, `WS_EX_TOOLWINDOW` et, si on veut des clics traversants, `WS_EX_TRANSPARENT`. `WS_EX_TOOLWINDOW` évite que le popup apparaisse dans Alt+Tab et dans la barre des tâches.

### 7.3 Autres règles

- Afficher avec `show()` puis ne jamais appeler `activateWindow()` ni `raise_()` de façon à voler le focus.
- Plein écran (jeux, vidéos, présentations) : détecter l'état « ne pas déranger » de Windows et, dans ce cas, n'afficher qu'un son discret ou rien (option).
- Multi-écran : si l'écran change entre deux dictées, recalculer la position avant l'apparition.

---

## 8. Textes et micro-copy

Tout est en français, en 1 à 4 mots, sans ponctuation lourde.

| Contexte | Texte |
| --- | --- |
| Écoute | `00:07` + puce `FR` |
| Aide (2 premières secondes) | Relâchez pour coller |
| Transcription | Transcription… |
| Succès | Collé |
| Audio trop court | Trop court |
| Aucun son | Aucun son détecté |
| Micro introuvable | Micro indisponible |
| Modèle en chargement | Chargement du modèle… |
| Erreur générique | Une erreur est survenue |
| Annulé (Échap pendant l'écoute) | Annulé |

**Annulation** : appuyer sur `Échap` pendant l'écoute annule l'enregistrement sans rien coller. À prévoir dès la v1, c'est un vrai confort.

---

## 9. Icône de la barre système

- **Forme** : un petit micro stylisé dans un cercle, trait de 1,5 px, version monochrome blanche (la barre des tâches est sombre) avec variante noire pour le thème clair.
- **États** : repos (gris clair), écoute (pastille rouge en bas à droite de l'icône), transcription (pastille bleu-violet), erreur (pastille ambre).
- **Tailles à fournir** : 16, 20, 24, 32 et 48 px (fichier `.ico` multi-résolution), pour tous les niveaux de DPI.
- **Menu au clic droit** : Activer/Désactiver · Modèle (medium, large-v3-turbo) · Langue · Position du popup · Réduire les animations · Ouvrir le dictionnaire de corrections · Lancer au démarrage de Windows · Quitter.

---

## 10. Sons (facultatif, désactivé par défaut)

- Début d'écoute : un « tic » très court et grave (60 ms, volume faible).
- Fin et collage : un « tac » un peu plus aigu (80 ms).
- Erreur : deux tons descendants, doux.

Les sons confirment l'action quand le popup est masqué ou quand tu regardes ailleurs. Prévoir un réglage de volume et un interrupteur.

---

## 11. Accessibilité et confort

- **Contraste** : texte principal sur fond sombre avec un ratio supérieur à 7:1 ; texte secondaire supérieur à 4,5:1.
- **Ne jamais compter sur la couleur seule** : chaque état a aussi une forme différente (point, arc tournant, coche, croix) et un texte.
- **Lecteurs d'écran** : définir `setAccessibleName` sur le popup et émettre l'état (« Enregistrement », « Transcription », « Collé »).
- **Taille de texte Windows** : respecter le réglage « Taille du texte » ; la pilule s'agrandit en hauteur de 84 à 96 px si nécessaire.
- **Fatigue visuelle** : pas d'animation rapide, pas de clignotement supérieur à 3 Hz.

---

## 12. Architecture technique (PySide6)

### 12.1 Classes

| Classe | Rôle |
| --- | --- |
| `OverlayWindow(QWidget)` | La fenêtre pilule : gère position, animations d'apparition, flux de fenêtre |
| `WaveformWidget(QWidget)` | Dessine les 32 barres, reçoit les niveaux, applique le lissage |
| `StatusDot(QWidget)` | Pastille d'état avec halo, rotation et coche |
| `OverlayController(QObject)` | Machine à états, reçoit les événements (touche, niveau audio, résultat) |
| `TrayIcon(QSystemTrayIcon)` | Icône et menu de la barre système |
| `AudioRecorder` | Capture micro, calcul du niveau, tampon audio pour Whisper |
| `Transcriber` | Charge faster-whisper, transcrit dans un thread séparé |
| `Settings` | Lecture et écriture du fichier JSON de configuration |

### 12.2 Threads et signaux

- **Thread principal** : toute l'interface.
- **Thread audio** (callback `sounddevice`) : calcule le niveau et émet un signal `level(float)`.
- **Thread transcription** : appelle Whisper, émet `finished(str)` ou `failed(str)`.
- **Hook clavier** (bibliothèque `keyboard`) : émet `pressed` et `released` vers le contrôleur.

Règle d'or : le thread audio et le thread transcription ne touchent jamais directement aux widgets. Ils passent par des signaux Qt (connexion automatique mise en file).

### 12.3 Boucle de rendu

```python
self.timer = QTimer(self)
self.timer.setInterval(16)          # environ 60 images par seconde
self.timer.timeout.connect(self.tick)

def tick(self):
    self.t += 0.016
    self.mettre_a_jour_barres()
    self.update()                   # redessine uniquement le waveform
```

Le timer **démarre à l'apparition et s'arrête à la disparition** : à l'état caché, l'app ne consomme aucun CPU.

### 12.4 Performance

- Limiter le redessin à la zone des waveforms (`update(rect)`).
- Mettre en cache le dégradé et le fond (pixmap) ; seules les barres sont redessinées à chaque image.
- Objectif : moins de 1 % de CPU pendant l'écoute et aucune perte d'images.

---

## 13. Réglages (fichier `settings.json`)

```json
{
  "popup": {
    "position": "bas-centre",
    "largeur": 420,
    "theme": "auto",
    "animations": true,
    "afficher_aide": true,
    "afficher_succes": true,
    "opacite_fond": 0.86
  },
  "audio": {
    "micro": "par-defaut",
    "sons": false
  },
  "whisper": {
    "modele": "medium",
    "langue": "fr",
    "initial_prompt": "Vocabulaire : implémentation, API, Electron, IGF, OmniLab."
  },
  "raccourci": "ctrl+alt+space"
}
```

Un second fichier `corrections.json` contient le dictionnaire de corrections post-transcription.

---

## 14. Cas limites à tester

1. Popup affiché pendant que le focus est dans Word, VS Code, un navigateur, WhatsApp Desktop : le collage doit toujours aller dans le champ actif.
2. Fenêtre plein écran (vidéo, jeu, présentation) : le popup reste visible ou se tait selon le réglage.
3. Écran externe branché, débranché, ou avec une mise à l'échelle différente.
4. Enregistrement très court (moins de 0,4 s) et très long (plus de 2 minutes).
5. Micro débranché ou désactivé pendant l'écoute.
6. Relâchement de la touche pendant l'animation d'apparition.
7. Deux dictées enchaînées très vite : la seconde ne doit pas être bloquée par l'animation de disparition de la première.
8. Fenêtre cible lancée en administrateur : afficher un avertissement clair.
9. Mise en veille puis réveil de Windows : le hook clavier et le micro doivent se réinitialiser.
10. Thèmes clair et sombre, effets de transparence désactivés dans Windows.

---

## 15. Plan de réalisation

| Étape | Contenu | Résultat |
| --- | --- | --- |
| 1 | `OverlayWindow` sans focus, fond, ombre, position | Pilule vide qui apparaît et disparaît proprement |
| 2 | `WaveformWidget` avec données simulées | Barres animées et lissage validés visuellement |
| 3 | Branchement du niveau micro réel | Barres qui suivent ta voix |
| 4 | Machine à états et pastille d'état | Écoute, transcription, succès, erreurs |
| 5 | Acrylique, thème clair/sombre, mouvement réduit | Finitions Windows 11 |
| 6 | Icône de la barre système et menu | App vivante en arrière-plan |
| 7 | Réglages JSON, dictionnaire de corrections, `initial_prompt` | Personnalisation |
| 8 | Démarrage avec Windows, empaquetage `.exe` (PyInstaller) | Version installable |

---

## 16. Checklist de validation finale

- [ ] Le popup ne vole jamais le focus.
- [ ] Les barres réagissent à la voix en moins de 50 ms.
- [ ] Le mouvement est fluide à 60 images par seconde, sans à-coups.
- [ ] Le popup est lisible sur fond blanc, fond noir et fond d'image chargée.
- [ ] Aucun CPU consommé à l'état caché.
- [ ] Tous les états ont une forme, une couleur et un texte distincts.
- [ ] L'annulation avec `Échap` fonctionne.
- [ ] L'app fonctionne en thème clair et en thème sombre.
- [ ] Le design reste agréable au bout de cinquante dictées dans la journée : c'est le vrai test de la discrétion.
