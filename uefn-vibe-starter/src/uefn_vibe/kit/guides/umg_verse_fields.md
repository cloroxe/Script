# UMG + champs Verse + View Bindings (UI avancée)

UMG = le designer visuel d'Unreal (User Widgets). Les **Verse Fields** sont des variables déclarées dans le
widget qu'on peut lire / écrire depuis Verse et **lier** à des propriétés du widget avec les **View Bindings**
(MVVM). C'est la voie pour : mise en page précise, polices, matériaux UI, animations pilotées par des données.

## Ce que dit la documentation Epic
- Fenêtre **Variables** du UMG Designer : on y ajoute des champs de types `logic`, `int`, `float`, `message`,
  `material`, `texture`, ainsi que des **événements**, qui peuvent porter des paramètres (int / float / logic).
- Les champs sont liés à des propriétés de widgets via **View Bindings** (valeur statique ou liée).
- Les champs sont reflétés dans le **digest Verse** du User Widget : c'est lui qui donne à Verse les
  noms et types exacts à utiliser.
- Un widget est référencé en Verse par son chemin de classe complet, par exemple (forme donnée par la doc) :
  `UserInterfaces.Verse.CustomButton.Widgets.UW_CustomButton{}`.
- Ajout à l'écran : `PlayerUI.SetFocus(Widget)` puis
  `PlayerUI.AddWidget(Widget, player_ui_slot{ InputMode := ui_input_mode.All })` ; retrait :
  `PlayerUI.RemoveWidget(Widget)`.

## Méthode pour l'agent (sans deviner l'API)
1. **Spécifie** l'écran : liste des champs (nom, type), des événements (avec paramètres) et ce que chacun pilote.
2. **Création du widget** : à faire dans le UMG Designer (voir « Ce que l'agent ne peut pas faire seul »).
3. **Lis le digest** du widget (`*.digest.verse` du projet) pour obtenir les noms / types / événements réels.
4. **Écris le Verse** : instancie la classe du widget, affecte les champs, abonne-toi aux événements,
   `AddWidget`. Un widget **par joueur**.
5. **Compile** (MCP officiel), corrige, **playtest**, observe.
6. Itère sur les liaisons (le plus fréquent : une propriété non liée → rien ne s'affiche).

## Ce que l'agent ne peut pas faire seul (état actuel)
- Le MCP officiel expose les toolsets Verse, Scene Graph, Device et Session : **pas** l'édition de User
  Widgets. Demande à l'utilisateur de créer le widget et ses champs dans le UMG Designer à partir de ta spec.
- Des projets communautaires créent des champs Verse et des liaisons MVVM par script Python. C'est
  **fragile** (risque de planter l'éditeur, champs perdus au rechargement si la sauvegarde ne régénère pas les
  tags du registre d'assets). N'y recours que sur une copie versionnée du projet, avec accord explicite.
- Problème signalé par la communauté : des champs de type vecteur / texture apparaissent dans le sélecteur de
  liaison mais la liaison ne se crée pas. Préfère `int`, `float`, `logic`, `message`.

## Modèle de spec à remplir avec l'utilisateur
```
Écran : <nom>            Classe widget : <UW_...>
Champs :   Score:int -> texte "Score : {Score}" | Vie:float -> largeur de la barre | Icone:texture -> image
Événements : BoutonJouer(PlayerIndex:int) -> démarre la partie
Données Verse -> champs : (qui écrit, quand)
Visibilité : par joueur, ouverte par <device>, fermée par <événement>
```
