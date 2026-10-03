# UEFN Vibe Starter

Un kit pour **créer une île Fortnite (UEFN) en parlant à une IA**, dans l'esprit de VibeStarter pour Roblox.
Ce n'est pas une application de bureau : c'est un **serveur MCP compagnon** que tu branches à ton agent
(Claude Code, Cursor, …) à côté du **MCP officiel d'Epic**.

```
 Ton agent IA ──┬── unreal-mcp   (officiel Epic, DANS UEFN, http://127.0.0.1:8000/mcp)
                │      Verse : lire / écrire / COMPILER · Devices · Scene Graph · PLAYTEST
                │
                └── uefn-vibe    (ce projet, stdio)
                       │  génère : Meshy (3D) · ElevenLabs (sons, voix) · OpenAI (icônes)
                       │  planifie : bâtiments modulaires · templates Verse · guides UI
                       ▼
                 vibe_bridge.py  (script Python DANS UEFN, 127.0.0.1:8765, jeton)
                       importe les assets · pose des acteurs · sauvegarde
```

## Ce que ça couvre

| Tu veux… | Comment |
|---|---|
| Objets 3D (clé **Meshy**) | `meshy_text_to_3d`, `meshy_image_to_3d`, `meshy_check` → FBX + textures PBR importés |
| Effets sonores (**ElevenLabs**) | `elevenlabs_sound_effect` (0,5–30 s, boucle possible) → WAV importé |
| Voix de PNJ / narration | `elevenlabs_speech` |
| Icônes (**OpenAI** Images) | `openai_icon` → PNG 1024², fond transparent → texture importée |
| Écrire, compiler, corriger du **Verse** | MCP officiel (toolset Verse) ; templates : `verse_template` |
| **Playtest** (start / stop / inspecter) | MCP officiel (toolset Session) |
| Placer des **devices**, régler leurs `@editable` | MCP officiel (toolset Device) |
| Poser des props importés, des **bâtiments** | `spawn_in_level`, `build_structure` (avec `dry_run`) |
| **UI** et interactions Verse | `uefn_guide("verse_ui")` + templates HUD / menu ; `uefn_guide("umg_verse_fields")` pour UMG + variables + liaisons |

> « ChatGPT » (l'abonnement) n'est pas l'API. Il te faut une **clé API OpenAI** (platform.openai.com).

## Installation (Windows, UEFN récent)

```powershell
py -m pip install -e .\uefn-vibe-starter
uefn-vibe-setup --project "C:\Users\toi\Documents\Fortnite Projects\MonIle"
```
Puis :
1. Ouvre `MonIle\VibeStarter\.env` et colle tes clés (`MESHY_API_KEY`, `ELEVENLABS_API_KEY`, `OPENAI_API_KEY`).
   Elles ne sont jamais écrites dans `.mcp.json` ni renvoyées à l'agent. Tu n'as besoin que des clés des services que tu utilises.
2. UEFN → **Project Settings** : active **Python Editor Scripting** et **UEFN MCP Toolsets** (les deux sont nécessaires).
3. Dans UEFN, lance le pont (console de sortie) : `py "C:\...\MonIle\VibeStarter\vibe_bridge.py"`.
4. Lance ton agent **depuis la racine du projet** (là où se trouvent `.mcp.json` et `AGENTS.md`) et demande :
   *« Appelle vibe_status, puis construis une petite arène : un bâtiment de départ, un bouton qui ouvre un menu, un HUD de score et un son de victoire. »*

`uefn-vibe-setup` crée `VibeStarter/` (pont, jeton, `.env`, `Inbox/`), écrit `.mcp.json` (en conservant tes serveurs),
`AGENTS.md` (les consignes de l'agent) et `CLAUDE.md`. Il ne remplace rien sans `--force`, et jamais ton `.env`.

## Windows : `.exe` (sans Python chez l'utilisateur final)

Un `.exe` Windows ne peut se construire que sous Windows (ou en CI). Deux scripts sont fournis dans `packaging/` :
- `build_exe.bat` : crée `dist\uefn-vibe-setup.exe` et `dist\uefn-vibe-mcp.exe` (PyInstaller). Garde-les dans le même dossier ;
  double-clique `uefn-vibe-setup.exe`, il te demande le dossier du projet et écrit `.mcp.json` pour pointer sur `uefn-vibe-mcp.exe`.
- `install.bat` : alternative **sans exe** (crée un `.venv` et installe le paquet).
- `build-windows.yml` : modèle GitHub Actions pour obtenir les exe sans rien installer (à copier dans `.github/workflows/`).

Ces scripts `.bat` n'ont **pas** été exécutés sous Windows (seule leur configuration PyInstaller l'a été, sous Linux).

## Garde-fous

- **Plafond de générations** par session (50 par défaut, `VIBE_MAX_GENERATIONS`) : une boucle d'agent ne vide pas tes crédits.
- L'agent ne peut importer / envoyer à un service **que des fichiers situés dans `VibeStarter/`** (les `..` et liens sont refusés).
- Le pont n'écoute que sur `127.0.0.1`, exige le jeton `X-Vibe-Token`, vérifie le `Host`, n'accepte que du JSON,
  valide chaque chemin Unreal, et exécute tout sur le thread principal de l'éditeur.
- Les messages d'erreur sont purgés des clés API.
- Si le pont est éteint, les assets sont **quand même générés** et l'outil indique où les glisser dans le Content Browser.

## Limites — à lire

**Ce qui est vérifié** : 89 tests automatiques (appels fournisseurs simulés d'après leurs docs, machine d'état Meshy
preview → texture → import, sécurité du pont avec un faux module `unreal`, installateur, transport stdio MCP réel,
packaging du wheel, et binaires PyInstaller **Linux** construits avec les mêmes options que sous Windows puis exécutés : installateur et serveur MCP).

**Ce qui ne l'est pas**, faute d'UEFN (Windows) et de clés dans l'environnement de développement :
- Le pont (`vibe_bridge.py`) n'a **jamais tourné dans un vrai UEFN**. Il utilise l'API Python d'Unreal
  (`AssetImportTask`, `EditorActorSubsystem`…) ; UEFN n'autorise qu'une partie de cette API et peut refuser des
  imports ou des propriétés. Premier réflexe en cas de souci : `vibe_status`, puis le journal de sortie d'UEFN.
- Les appels réels à Meshy, ElevenLabs et OpenAI n'ont **pas** été faits avec de vraies clés. Les formes de requêtes suivent
  leur documentation (Meshy v2 text-to-3d / v1 image-to-3d, ElevenLabs sound-generation, OpenAI `gpt-image-1`).
  Le modèle d'image se règle avec `OPENAI_IMAGE_MODEL`.
- Les **templates Verse** (`vibe_hud`, `vibe_menu`) ne sont **pas compilés** : ce sont des points de départ ; l'agent doit
  les compiler avec le MCP officiel et corriger.
- **UMG** : l'agent ne peut pas créer seul un User Widget ni ses champs Verse (le MCP officiel n'expose pas cette
  édition ; les scripts communautaires sont fragiles). Le guide `umg_verse_fields` décrit le flux : tu poses le widget et
  ses variables dans le UMG Designer à partir d'une spec rédigée par l'agent, puis l'agent écrit tout le Verse
  (instanciation, champs, événements, liaisons côté code) et boucle compile + playtest.
- Les bâtiments supposent des modules de mur à pivot centré, longueur sur X ; les repères éditeur (cm) et Verse (m) diffèrent.
- Les imports FBX/audio dans UEFN sont soumis à ses propres règles de validation et de contenu : n'importe que ce que tu as le droit d'utiliser.

## Développement

```bash
pip install -e "./uefn-vibe-starter[dev]"
cd uefn-vibe-starter && python -m pytest
```
