# Workflow de référence

## Boucle de création
1. **Cadrer** : mode de jeu en une phrase, 3 mécaniques maximum, public, durée d'une partie.
2. **Squelette Verse** : un `creative_device` par responsabilité (score, rounds, UI, spawn…). Compile.
3. **Layout** : devices et entités via le MCP officiel ; bâtiments via `build_structure`.
4. **Assets** : génère et importe seulement ce qui est nécessaire au prochain test.
5. **Interactions** : relie devices et Verse (`@editable`, `.Subscribe(...)`).
6. **Playtest** (toolset Session du MCP officiel) : démarre, observe, arrête. UEFN utilise
   Play-in-Client, pas Play-in-Editor.
7. **Corrige** d'après les logs, puis recommence à l'étape 5.

## Verse : cycle de validation
- Après CHAQUE modification : compile (toolset Verse du MCP officiel). Zéro erreur avant d'avancer.
- « Push Verse Changes » (mise à jour rapide du code seul) existe dans UEFN après une compilation réussie.
- Lis les messages d'erreur du compilateur en entier : ils nomment la ligne et le type attendu.
- Pour la syntaxe d'un device : lis le fichier `*.digest.verse` du projet (déclarations réelles de ta version
  d'UEFN) plutôt que de deviner une signature.

## Limites connues (à connaître avant de s'énerver)
- Le MCP officiel signale un décalage de repères entre XYZ (éditeur) et Left-Up-Forward (Verse) : vérifie les
  positions visuellement après un placement.
- L'éditeur peut se figer brièvement pendant un appel MCP : attends, ne relance pas en rafale.
- Python dans UEFN ne peut modifier que les propriétés autorisées par la validation d'UEFN.
  Utilise un contrôle de version avant d'automatiser en masse.
