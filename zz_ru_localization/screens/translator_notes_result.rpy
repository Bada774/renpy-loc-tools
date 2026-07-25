screen translator_notes_result(enabled):
    zorder 200
    modal True
    style_prefix "translator_notes_result"

    if enabled:
        add Transform("images/bonus/achievement_image_22_pic_01.webp", blur=10)
    else:
        add Transform("images/Character-Scenes/ARJ/s002/sm1cs-arj002-33 mc-arj-sy-smile-waiting.webp", blur=10)

    frame:
        style "translator_notes_result_outer_frame"

        vbox:
            style "translator_notes_result_vbox"

            if enabled:
                text _("Спасибо, что цените труд переводчика!") style "translator_notes_result_text"

                null height 30

                text _("Теперь Вы будете видеть подсказки.") style "translator_notes_result_text"

                text _("Надеюсь, они помогут Вам еще больше насладиться историей!") style "translator_notes_result_text"

                null height 30

                text _("Приятной игры!") :
                    style "translator_notes_result_text"
            else:
                text _("Подсказки отключены!") style "translator_notes_result_text"

                text _("Вы всегда можете изменить свой выбор в настройках.") style "translator_notes_result_text"

                null height 30

                text _("Приятной игры!") style "translator_notes_result_text"

            null height 30
            textbutton _("Начать"):
                action Return()
                style "translator_notes_result_button"

init -1 style translator_notes_result_outer_frame is translator_notes_choice_outer_frame
init -1 style translator_notes_result_vbox is translator_notes_choice_vbox
init -1 style translator_notes_result_text is translator_notes_choice_text
init -1 style translator_notes_result_label is translator_notes_choice_label
init -1 style translator_notes_result_label_text is translator_notes_choice_label_text
init -1 style translator_notes_result_button is translator_notes_choice_button
init -1 style translator_notes_result_button_text is translator_notes_choice_button_text

init -1 style translator_notes_result_vbox:
    spacing 20

init -1 style translator_notes_result_text:
    size 28

init -1 style translator_notes_result_button:
    xalign 0.5
    top_margin 20