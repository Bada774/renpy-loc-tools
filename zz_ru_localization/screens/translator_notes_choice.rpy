define -2 gui.ru_accent_color = "#a04de4"

define -2 gui.ru_hover_color = "#e053c9"

define -2 gui.ru_text_color = "#F9EEEF"

define -2 gui.ru_text_outline_color = "#3a2033"

define -2 gui.ru_subtext_color = "#CCCCCC"

define -2 gui.ru_subtext_outline_color = "#333032"

define -2 gui.ru_frame_borders = Borders(25, 25, 25, 25)

define -2 gui.ru_background_color = "#000000"

define -2 gui.ru_background_color_alpha = 1

define -2 gui.ru_notify_accent_color = gui.ru_accent_color
define -2 gui.ru_notify_hover_color = gui.ru_hover_color
define -2 gui.ru_button_idle_color = gui.ru_accent_color
define -2 gui.ru_button_hover_color = gui.ru_hover_color


screen translator_notes_choice():
    zorder 200
    modal True
    style_prefix "translator_notes_choice"

    add Transform("gui/mainmenu/main_menu_bg_3.webp", blur=10)

    frame:
        style "translator_notes_choice_outer_frame"

        vbox:
            style "translator_notes_choice_vbox"

            text _("КОММЕНТАРИИ ПЕРЕВОДЧИКА")
            
            null height 40

            text _("Этот перевод содержит дополнительные пояснения к моментам, которые могут плохо восприниматься в контексте диалога, вроде локальных шуток, отсылок, игр слов, которые сложно адаптировать."):
                style "translator_notes_choice_text"

            null height 10

            text _("Такие места будут выделятся в виде цветных ссылок прямо в тексте диалогов, на которые Вы можете навести курсор. Пояснение будет показано в виде уведомления в верхней части экрана."):
                style "translator_notes_choice_text"

            null height 30

            $ test_note_text = "{{a=ru_note:{hint}}}{word}{{/a}}".format(
                hint=_("Отлично! Именно так будут выглядеть пояснения к переводу в игре."),
                word=_("ссылкой")
            )
            vbox:
                spacing 10

                text _("Пример:") style "translator_notes_choice_preview_text"

                text "\"Речь классного и красивого персонажа с [test_note_text] внутри\"" style "translator_notes_choice_link_text"

            null height 30

            text _("Вы хотите включить их отображение?\n(Эту настройку всегда можно будет изменить в меню \"Настройки\" -> \"Диалоги\")") :
                style "translator_notes_choice_subtext"

            hbox:
                style "translator_notes_choice_hbox"

                textbutton _("Включить"):
                    action Return(True)
                    style "translator_notes_choice_button"

                textbutton _("Отключить"):
                    action Return(False)
                    style "translator_notes_choice_button"

init -1 style translator_notes_choice_outer_frame is empty
init -1 style translator_notes_choice_vbox is vbox
init -1 style translator_notes_choice_label is gui_label
init -1 style translator_notes_choice_label_text is gui_label_text
init -1 style translator_notes_choice_text is gui_text
init -1 style translator_notes_choice_subtext is gui_text
init -1 style translator_notes_choice_hbox is hbox
init -1 style translator_notes_choice_button is button
init -1 style translator_notes_choice_button_text is button_text
init -1 style translator_notes_choice_preview_text is gui_text

init -1 style translator_notes_choice_outer_frame:
    xalign 0.5
    yalign 0.5
    xsize 1000
    padding (50, 50)

init -1 style translator_notes_choice_vbox:
    xalign 0.5
    spacing 25

init -1 style translator_notes_choice_label:
    xalign 0.5

init -1 style translator_notes_choice_label_text:
    xalign 0.5
    text_align 0.5
    size 45
    color gui.ru_accent_color

init -1 style translator_notes_choice_text:
    xalign 0.5
    text_align 0.5
    size 28
    outlines [(2, gui.ru_text_outline_color, 1, 1)]
    color gui.ru_text_color

init -1 style translator_notes_choice_subtext:
    xalign 0.5
    text_align 0.5
    size 22
    color gui.ru_subtext_color
    outlines [(1, gui.ru_subtext_outline_color, 1, 1)]

init -1 style translator_notes_choice_hbox:
    xalign 0.5
    spacing 150
    top_margin 30

init -1 style translator_notes_choice_preview_text:
    xalign 0.5
    text_align 0.5
    size 30
    outlines [(1, gui.ru_text_outline_color, 1, 1)]
    color gui.ru_text_color

init -1 style translator_notes_choice_link_text is gui_text:
    yalign 0.5
    size 30
    outlines []
    color gui.ru_text_color

init -1 style translator_notes_choice_button:
    xalign 0.5
    padding (50, 15)
    idle_background Fixed(
        Transform(Frame("gui/others/alpha/frame_background_only.webp", gui.ru_frame_borders, tile=gui.frame_tile), matrixcolor=TintMatrix(gui.ru_background_color), alpha=gui.ru_background_color_alpha),
        Transform(Frame("gui/others/alpha/frame_border_only.webp", gui.ru_frame_borders, tile=gui.frame_tile), matrixcolor=TintMatrix(gui.ru_button_idle_color))
    )
    hover_background Fixed(
        Transform(Frame("gui/others/alpha/frame_background_only.webp", gui.ru_frame_borders, tile=gui.frame_tile), matrixcolor=TintMatrix(gui.ru_background_color), alpha=gui.ru_background_color_alpha),
        Transform(Frame("gui/others/alpha/frame_border_only.webp", gui.ru_frame_borders, tile=gui.frame_tile), matrixcolor=TintMatrix(gui.ru_button_hover_color))
    )
    activate_sound audio.sfx_menu_button_click
    hover_sound audio.sfx_menu_button_hover

init -1 style translator_notes_choice_button_text:
    size 35
    idle_color gui.ru_text_color
    hover_color gui.ru_text_color
    xalign 0.5
    yalign 0.5
