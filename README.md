# Convertisseur d'images App Store LifeFlow

Petit outil local, hors ligne et compatible Windows pour préparer des images promotionnelles destinées à App Store Connect. Il utilise Python et Pillow, sans service externe ni IA générative.

## Installation et utilisation

Depuis ce dossier, avec Python 3.9 ou plus récent :

```powershell
py -m pip install -r requirements.txt
py main.py
```

Sous Windows, `python` peut pointer vers le raccourci du Microsoft Store plutôt que vers l’installation de Python. Utilisez `py` pour lancer le programme et installer ses dépendances.

Déposez les images dans `input\`. Les fichiers PNG, JPG, JPEG et WebP sont pris en charge. Le programme crée les dossiers manquants, traite toutes les images et écrit les PNG dans un sous-dossier par format, par exemple `output\1320x2868\`.

Pour ne produire qu'un format configuré :

```powershell
py main.py --size 1320x2868
```

Les images sources ne sont jamais modifiées. En cas d'erreur sur une image ou un format, le programme la signale et continue le traitement des autres.

## Configuration

Modifiez `config.json` :

- `target_sizes` : liste des dimensions de sortie autorisées : 2556 × 1179, 1179 × 2556, 2622 × 1206 et 1206 × 2622. Vous pouvez retirer des formats de la configuration, mais toute autre dimension sera rejetée.
- `extension_mode` : `gradient` (échantillonnage et interpolation des couleurs des bords) ou `blur` (même extension adoucie).
- `fallback_color` : couleur de secours au format hexadécimal.
- `sharpening` : accentuation optionnelle de 0 à 2, appliquée uniquement lors d'un agrandissement; 0 la désactive.
- `inner_margin` : marge intérieure en pixels, facultative; 0 désactive cette marge.
- `output_format` : doit rester `PNG`.
- `png_compress_level` : compression PNG sans perte de 0 à 9.

L'image est redimensionnée proportionnellement avec LANCZOS, entièrement visible et centrée. Le fond étendu s'appuie sur les couleurs de bord et ne reprend pas les éléments du premier plan. La transparence et le profil ICC sont préservés quand c'est possible. Un agrandissement classique ne peut pas recréer les détails absents de l'image source.

## Tests

Depuis ce dossier :

```powershell
py -m unittest discover -s tests -v
```
