default current_ru_note = None

init python:
    if persistent.ru_notes_enabled is None:
        persistent.ru_notes_enabled = True

    _old_hyperlink_styler = config.hyperlink_styler
    _old_hyperlink_focus = config.hyperlink_focus

    def ru_note_styler(target):
        if target and target.startswith("ru_note:"):
            return style.ru_note_link_style
        if _old_hyperlink_styler:
            return _old_hyperlink_styler(target)
        return style.hyperlink_text

    def ru_note_focus(target):
        global current_ru_note
        
        if target and target.startswith("ru_note:"):
            hint_text = target[8:]
            if current_ru_note != hint_text:
                current_ru_note = hint_text
                renpy.show_screen("ru_note_notify", message=hint_text)
                renpy.restart_interaction()
        else:
            if current_ru_note is not None:
                current_ru_note = None
                renpy.hide_screen("ru_note_notify")
                renpy.restart_interaction()
                
        if _old_hyperlink_focus:
            return _old_hyperlink_focus(target)
        return None

    config.hyperlink_styler = ru_note_styler
    config.hyperlink_focus = ru_note_focus
    
    config.hyperlink_handlers["ru_note"] = lambda target: None

    def note(word, hint):
        if persistent.ru_notes_enabled:
            return "{{a=ru_note:{hint}}}{word}{{/a}}".format(hint=hint, word=word)
        else:
            return word


screen ru_note_notify(message):
    zorder 300
    style_prefix "notify"

    frame at notify_appear:
        xalign 0.5
        background Fixed(
            Transform(Frame("gui/others/alpha/notify_background_only.webp", gui.notify_frame_borders, tile=gui.frame_tile), matrixcolor=TintMatrix(gui.ru_background_color), alpha=gui.ru_background_color_alpha),
            Transform(Frame("gui/others/alpha/notify_border_only.webp", gui.notify_frame_borders, tile=gui.frame_tile), matrixcolor=TintMatrix(gui.ru_accent_color))
            )
        padding gui.notify_frame_borders.padding
        text "[message!t]" style "notify_text"


init -1 style ru_note_link_style is hyperlink_text:
    color gui.ru_notify_accent_color
    hover_color gui.ru_notify_hover_color
    hover_underline False