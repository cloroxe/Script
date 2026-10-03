# Consignes pour l'agent — projet UEFN avec Vibe Starter

Tu construis une île Fortnite dans UEFN avec deux serveurs MCP :

| Serveur | Rôle |
|---|---|
| `unreal-mcp` (officiel Epic, dans l'éditeur) | Lire / écrire / **compiler le Verse**, entités Scene Graph, **placer et configurer les devices**, **lancer / arrêter / inspecter un playtest** |
| `uefn-vibe` (ce projet) | Générer des assets (Meshy 3D, ElevenLabs sons et voix, OpenAI icônes), les **importer** dans le Content Browser, poser des acteurs, planifier des bâtiments, templates Verse, guides |

## Démarrage de chaque session
1. `vibe_status` : clés présentes ? pont UEFN joignable ? MCP officiel joignable ? Corrige avant de continuer.
2. `uefn_guide(topic="workflow")` puis le guide du sujet (`assets`, `verse_ui`, `umg_verse_fields`, `building`).

## Règles
- **Jamais de clé API** dans le chat, le code, un commit ou `.mcp.json`. Elles vivent dans `VibeStarter/.env`.
- **Petit pas, preuve à chaque pas** : Verse modifié → compile avec l'outil Verse du MCP officiel → corrige jusqu'à zéro erreur → playtest → lis les logs. Ne dis jamais « ça marche » sans compile + playtest.
- Les templates Verse (`verse_template`) et les extraits des guides sont des **points de départ non garantis**. Le compilateur a toujours raison.
- Demande confirmation avant de supprimer / écraser des assets, des fichiers Verse ou de poser plus de 200 acteurs.
- Coûts : les générations Meshy / ElevenLabs / OpenAI consomment des crédits. Génère un asset à la fois, vérifie, puis continue. Ne régénère pas en boucle. Un plafond de générations par session existe (`vibe_status` → `generations`) ; s'il est atteint, demande à l'utilisateur avant de continuer.
- Noms d'assets : lettres, chiffres, `_`. Préfixes : `SM_` modèles, `SFX_` / `VO_` sons, `T_Icon_` icônes (ajoutés automatiquement).
- Respecte les règles de contenu de Fortnite / UEFN : n'importe que des assets que l'utilisateur a le droit d'utiliser.

## Choisir le bon outil
- Un objet 3D → `meshy_text_to_3d` (ou `meshy_image_to_3d` depuis une icône / concept dans `VibeStarter/`).
- Un son d'ambiance, d'impact, d'UI → `elevenlabs_sound_effect` ; une réplique → `elevenlabs_speech`.
- Une icône d'objet, de quête, de bouton → `openai_icon`.
- Poser des devices / entités / lire des propriétés `@editable` → MCP officiel.
- Poser des props importés ou des bâtiments modulaires → `spawn_in_level`, `build_structure` (d'abord `dry_run`).
- Écrire du Verse / jouer → MCP officiel ; `verse_template` pour démarrer.
- Interface : voir `verse_ui` (UI en code) et `umg_verse_fields` (UMG + variables Verse + liaisons).
