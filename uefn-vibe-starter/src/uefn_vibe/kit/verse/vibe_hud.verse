# TEMPLATE Vibe Starter — HUD de score par joueur (UI en code).
# Écrit d'après la documentation Epic, NON compilé par l'auteur du kit : compile avec l'outil Verse du
# MCP officiel et corrige les erreurs avant usage. Exemple d'appel : Hud.AddScore(Player, 10)

using { /Fortnite.com/Devices }
using { /Verse.org/Colors }
using { /Verse.org/Simulation }
using { /UnrealEngine.com/Temporary/SpatialMath }
using { /UnrealEngine.com/Temporary/UI }

__CLASS_NAME__ := class(creative_device):

    var Labels : [player]text_block = map{}
    var Scores : [player]int = map{}

    ScoreText<localizes>(Value : int) : message = "Score : {Value}"

    OnBegin<override>()<suspends> : void =
        for (Player : GetPlayspace().GetPlayers()):
            AddHud(Player)
        GetPlayspace().PlayerAddedEvent().Subscribe(OnPlayerAdded)
        GetPlayspace().PlayerRemovedEvent().Subscribe(OnPlayerRemoved)

    OnPlayerAdded(Player : player) : void =
        AddHud(Player)

    OnPlayerRemoved(Player : player) : void =
        var KeptLabels : [player]text_block = map{}
        var KeptScores : [player]int = map{}
        for (Key -> Label : Labels, Key <> Player):
            if (set KeptLabels[Key] = Label) {}
        for (Key -> Value : Scores, Key <> Player):
            if (set KeptScores[Key] = Value) {}
        set Labels = KeptLabels
        set Scores = KeptScores

    AddHud(Player : player) : void =
        if (PlayerUI := GetPlayerUI[Player], not Labels[Player]):
            Label := text_block{DefaultText := ScoreText(0), DefaultTextColor := NamedColors.White}
            Root := canvas:
                Slots := array:
                    canvas_slot:
                        Anchors := anchors{Minimum := vector2{X := 0.5, Y := 0.0}, Maximum := vector2{X := 0.5, Y := 0.0}}
                        Offsets := margin{Top := 32.0}
                        Alignment := vector2{X := 0.5, Y := 0.0}
                        SizeToContent := true
                        Widget := Label
            PlayerUI.AddWidget(Root)
            if (set Labels[Player] = Label) {}
            if (set Scores[Player] = 0) {}

    AddScore(Player : player, Amount : int) : void =
        if (Label := Labels[Player], Current := Scores[Player]):
            Next := Current + Amount
            if (set Scores[Player] = Next) {}
            Label.SetText(ScoreText(Next))
