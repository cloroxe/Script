# Assets : Meshy, ElevenLabs, OpenAI

## Import
Tous les outils génèrent dans `VibeStarter/Inbox/{Models,Audio,Textures}` puis importent via le pont dans
`<Projet>/VibeStarter/{Models,Audio,Textures}` du Content Browser. Si le pont est éteint, l'outil renvoie
`manual_import` : fais glisser les fichiers dans le Content Browser (aucune génération n'est perdue).
Lance `save_project` après un lot d'imports.

## 3D — Meshy
- Format importé : **FBX**. Textures PBR (base color, normal, metallic, roughness) importées en plus quand `textured=True`.
- Géométrie : vise 5 000–20 000 triangles pour un prop ; moins pour ce qui est répété (≤ 3 000).
- Prompt : sujet + matière + style + « single object, game asset ». Une chose par prompt (pas une scène).
- Durée : plusieurs minutes. Si `status="pending"`, appelle `meshy_check(name)`.
- Après import, vérifie échelle / pivot dans l'éditeur ; ajuste avec `spawn_in_level(scale=...)`.

## Sons — ElevenLabs
- Sortie : WAV 16 bits mono (UEFN accepte .wav, .aif, .flac, .ogg). 0,5–30 s par effet.
- Prompt SFX : décris le son physiquement (« heavy wooden door slam, short echo »), pas le jeu.
- `loop=true` pour les ambiances. `prompt_influence` haut = plus fidèle au texte.
- Voix : `elevenlabs_speech` avec un `voice_id` de ton compte ElevenLabs.
- Lecture en jeu : place un audio player device (MCP officiel) et assigne le son importé.

## Icônes — OpenAI
- PNG 1024×1024, fond transparent par défaut. Indique style + sujet ; pas de texte dans l'image.
- Idéal pour l'inventaire, les quêtes, les boutons. L'import crée une texture ; l'affecter à un widget se fait
  côté UI (`verse_ui` / `umg_verse_fields`).
- Cohérence : réutilise le même paramètre `style` pour toute une famille d'icônes.
