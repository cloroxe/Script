# Bâtiments et placement

## Unités
- Le pont et `build_structure` utilisent les **coordonnées de l'éditeur : centimètres, X avant, Y droite, Z haut**.
- Verse travaille en mètres avec un repère différent (le MCP officiel signale le décalage XYZ / Left-Up-Forward).
  Ne mélange pas les deux sans conversion ; contrôle visuellement.

## build_structure
1. Importe (ou choisis) un module de **mur**, de **sol**, de **toit**, éventuellement un **cadre de porte**.
   Convention attendue : longueur du mur sur l'axe X local, pivot centré, largeur = `module_cm`.
2. Appelle `build_structure(..., dry_run=true)` : tu obtiens le décompte par rôle et un échantillon.
3. Valide les dimensions, puis relance avec `dry_run=false`.
- Plafond de sécurité : 2 000 pièces par appel. Pour de grandes structures, assemble plusieurs appels.
- Si un module n'a pas la bonne orientation, tourne tout le bâtiment avec `yaw_deg` ou corrige le pivot du mesh.

## Devices et Scene Graph
Interactions (boutons, triggers, spawners, barrières, audio…) : toolset **Device** du MCP officiel
(catalogue, placement, propriétés `@editable`). Entités et composants : toolset **Entity / Scene Graph**.
Pour qu'un device soit pilotable en Verse : déclare `@editable Nom : type_du_device = type_du_device{}` dans ton
`creative_device`, puis relie l'instance dans l'éditeur.
