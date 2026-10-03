# TEMPLATE Vibe Starter — menu à boutons ouvert par un button device (UI en code).
# Écrit d'après la documentation Epic, NON compilé par l'auteur du kit : compile avec l'outil Verse du
# MCP officiel et corrige les erreurs avant usage.
# Dans l'éditeur : assigne OpenButton à un Button Device placé dans le niveau.

using { /Fortnite.com/Devices }
using { /Verse.org/Colors }
using { /Verse.org/Simulation }
using { /UnrealEngine.com/Temporary/SpatialMath }
using { /UnrealEngine.com/Temporary/UI }

__CLASS_NAME__ := class(creative_device):

    @editable OpenButton : button_device = button_device{}

    var Menus : [player]canvas = map{}

    TitleText<localizes> : message = "Menu"
    PlayText<localizes> : message = "Jouer"
    CloseText<localizes> : message = "Fermer"

    OnBegin<override>()<suspends> : void =
        OpenButton.InteractedWithEvent.Subscribe(OnOpenPressed)

    OnOpenPressed(Agent : agent) : void =
        if (Player := player[Agent], PlayerUI := GetPlayerUI[Player], not Menus[Player]):
            Title := text_block{DefaultText := TitleText, DefaultTextColor := NamedColors.White}
            PlayButton := button_regular{DefaultText := PlayText}
            CloseButton := button_regular{DefaultText := CloseText}
            PlayButton.OnClick().Subscribe(OnPlayPressed)
            CloseButton.OnClick().Subscribe(OnClosePressed)
            Root := canvas:
                Slots := array:
                    canvas_slot:
                        Anchors := anchors{Minimum := vector2{X := 0.5, Y := 0.5}, Maximum := vector2{X := 0.5, Y := 0.5}}
                        Alignment := vector2{X := 0.5, Y := 0.5}
                        SizeToContent := true
                        Widget := stack_box:
                            Orientation := orientation.Vertical
                            Slots := array:
                                stack_box_slot{Widget := Title}
                                stack_box_slot{Widget := PlayButton}
                                stack_box_slot{Widget := CloseButton}
            PlayerUI.AddWidget(Root, player_ui_slot{InputMode := ui_input_mode.All})
            if (set Menus[Player] = Root) {}

    OnPlayPressed(Message : widget_message) : void =
        # TODO : démarrer la partie pour Message.Player
        CloseMenu(Message.Player)

    OnClosePressed(Message : widget_message) : void =
        CloseMenu(Message.Player)

    CloseMenu(Player : player) : void =
        if (PlayerUI := GetPlayerUI[Player], Root := Menus[Player]):
            PlayerUI.RemoveWidget(Root)
            var Kept : [player]canvas = map{}
            for (Key -> Value : Menus, Key <> Player):
                if (set Kept[Key] = Value) {}
            set Menus = Kept
