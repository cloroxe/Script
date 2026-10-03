# UI en code Verse (module `/UnrealEngine.com/Temporary/UI`)

À utiliser pour : HUD simples, menus à boutons, textes qui changent. Tout est décrit en Verse, donc
**compilable et testable par l'agent**. Limite : la mise en forme fine (polices, matériaux, animations)
est limitée — pour une UI « ultra poussée », passe à UMG (`umg_verse_fields`).

## Motifs confirmés par la documentation Epic
```verse
if (PlayerUI := GetPlayerUI[Player]):
    PlayerUI.AddWidget(Widget)                                            # afficher
    PlayerUI.AddWidget(Widget, player_ui_slot{ InputMode := ui_input_mode.All })   # afficher + curseur / focus UI
    PlayerUI.RemoveWidget(Widget)                                         # masquer
```
Abonnement à un événement : `Device.UnEvenement.Subscribe(MaFonction)`. L'annulation se fait via la valeur
`cancelable` renvoyée par `Subscribe`.

## Architecture recommandée
- **Une UI par joueur** : stocke les widgets dans un `var X : [player]widget_ou_text_block = map{}`.
- Crée l'UI quand un joueur arrive (`GetPlayspace().PlayerAddedEvent()`), nettoie quand il part
  (`PlayerRemovedEvent()`). Reconstruis la map sans la clé du joueur parti (les maps Verse sont des valeurs).
- Sépare **données** (score, vie…) et **vue** (widgets) : une fonction `Refresh(Player)` relit les données et
  met à jour les widgets (`SetText`, etc.).
- Texte affiché = type `message` : déclare `MonTexte<localizes>(Valeur:int):message = "Score : {Valeur}"`.
- Interaction : `button_device.InteractedWithEvent` ouvre un menu ; un bouton de widget expose `OnClick()`.
  Le message reçu contient le joueur concerné.
- Mode d'entrée `ui_input_mode.All` pour un menu cliquable ; retire le widget pour rendre le contrôle au joueur.

## Templates fournis
`verse_template("vibe_hud", class_name=...)` : HUD de score par joueur.
`verse_template("vibe_menu", class_name=...)` : menu à boutons ouvert par un button device.
**Ils n'ont pas été compilés par l'auteur du kit** : compile, lis les erreurs, corrige.

## Relier à d'autres devices (interactions)
```verse
# dans un autre creative_device
@editable Hud : vibe_hud = vibe_hud{}      # nom de classe choisi pour le template HUD
OnCollected(Agent : agent) : void =
    if (Player := player[Agent]):
        Hud.AddScore(Player, 10)
```
Place les deux devices dans le niveau, assigne `Hud` dans le panneau de détails de l'éditeur.
