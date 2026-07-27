"""
FLSM-specific hints for add_context.py.

The core doesn't know anything about this game's data conventions - it just
asks build_hints() for three lookup tables and inserts them wherever a
matching anchor (label, dict key, chat message text) turns up while walking
context. Everything here is what would break on a different game:

  - NAME_CATALOGUE = {"io-xxx": {...}, ...}
    (interaction_character_options.rpy, interaction_location_options.rpy,
     interaction_object_options.rpy)
  - <someone>.interactions = [{LABEL: "...", ...}, ...]  (q_inter_*.rpy)
  - the quest list, where CHAR_INTR: {"code": "io-id"} and
    CHAT: {"code": "chat-key"} (including nested under OFFRAMP) are the only
    place an interaction/chat gets tied to a character
  - chat catalogues: <cat>["key"] = [{SENDER, CONTENT, CHOICES, ...}, ...]
"""

import ast
import os
import re

CATALOGUE_ASSIGN_RE = re.compile(r'^\s*\w*CATALOGUE\s*=\s*\{')
INTERACTIONS_ASSIGN_RE = re.compile(r'^\s*(?:\$\s+)?[\w\.\(\)"\'\s]*\.interactions\s*=\s*\[')
CHAR_INTR_RE = re.compile(r'CHAR_INTR\s*:\s*\{\s*["\'](\w+)["\']\s*:\s*["\']([^"\']+)["\']\s*\}')
CHAT_RE = re.compile(r'CHAT\s*:\s*\{\s*["\'](\w+)["\']\s*:\s*["\']([^"\']+)["\']\s*\}')
CHAT_CATALOGUE_ASSIGN_RE = re.compile(r'^\s*\w+\[\s*["\'][^"\']+["\']\s*\]\s*=\s*\[\s*$')


def _iter_rpy_files(source_root):
    for root, dirs, files in os.walk(source_root):
        dirs[:] = [d for d in dirs if d != 'tl']
        for f in files:
            if f.endswith(".rpy"):
                yield os.path.join(root, f)


def _read_lines(filepath, cache):
    if filepath not in cache:
        if not os.path.exists(filepath):
            cache[filepath] = None
        else:
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                cache[filepath] = f.readlines()
    return cache[filepath]


def _node_to_str(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Constant):
        return str(node.value) if not isinstance(node.value, str) else node.value
    if isinstance(node, (ast.List, ast.Tuple)):
        inner = ", ".join(_node_to_str(e) for e in node.elts)
        ob, cb = ("[", "]") if isinstance(node, ast.List) else ("(", ")")
        return f"{ob}{inner}{cb}"
    if isinstance(node, ast.Dict):
        parts = [f"{_node_to_str(k)}: {_node_to_str(v)}" for k, v in zip(node.keys, node.values) if k is not None]
        return "{" + ", ".join(parts) + "}"
    if isinstance(node, ast.Attribute):
        return f"{_node_to_str(node.value)}.{node.attr}"
    if isinstance(node, ast.Call):
        return f"{_node_to_str(node.func)}({', '.join(_node_to_str(a) for a in node.args)})"
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return f"-{_node_to_str(node.operand)}"
    return ast.dump(node)


def _collect_bracketed_chunk(lines, start_idx):
    chunk, depth, opened, i = [], 0, False, start_idx
    while i < len(lines):
        chunk.append(lines[i])
        for ch in lines[i]:
            if ch in "[{":
                depth += 1
                opened = True
            elif ch in "]}":
                depth -= 1
        i += 1
        if opened and depth <= 0:
            break
    return chunk, i


def build_catalogue_conditions(source_root, lines_cache=None):
    """id -> "FIELD=val, FIELD=val" for CATALOGUE dicts and .interactions lists."""
    if lines_cache is None:
        lines_cache = {}
    conditions = {}

    for path in _iter_rpy_files(source_root):
        lines = _read_lines(path, lines_cache)
        if not lines:
            continue

        i = 0
        while i < len(lines):
            is_catalogue = CATALOGUE_ASSIGN_RE.match(lines[i])
            is_interactions = INTERACTIONS_ASSIGN_RE.match(lines[i])
            if not (is_catalogue or is_interactions):
                i += 1
                continue

            chunk, i = _collect_bracketed_chunk(lines, i)
            rhs = "".join(chunk).split('=', 1)[1]
            try:
                tree = ast.parse(rhs.strip(), mode='eval')
            except SyntaxError:
                continue

            if is_catalogue and isinstance(tree.body, ast.Dict):
                for k, v in zip(tree.body.keys, tree.body.values):
                    if k is None or not isinstance(v, ast.Dict):
                        continue
                    entry_id = _node_to_str(k)
                    extras = [f"{_node_to_str(fk)}={_node_to_str(fv)}" for fk, fv in zip(v.keys, v.values)
                              if fk is not None and _node_to_str(fk) != "NAME"]
                    if extras:
                        conditions[entry_id] = ", ".join(extras)

            elif is_interactions and isinstance(tree.body, ast.List):
                for item in tree.body.elts:
                    if not isinstance(item, ast.Dict):
                        continue
                    label, extras = None, []
                    for k, v in zip(item.keys, item.values):
                        if k is None:
                            continue
                        kname = _node_to_str(k)
                        if kname == "LABEL":
                            label = _node_to_str(v)
                        else:
                            extras.append(f"{kname}={_node_to_str(v)}")
                    if label and extras:
                        conditions[label] = ", ".join(extras)

    return conditions


def build_character_index(source_root, lines_cache=None):
    """io-id / chat-key -> character codename, read off the quest list's CHAR_INTR/CHAT fields."""
    if lines_cache is None:
        lines_cache = {}
    io_to_char, chat_to_char = {}, {}

    for path in _iter_rpy_files(source_root):
        lines = _read_lines(path, lines_cache)
        if not lines:
            continue
        text = "".join(lines)
        for m in CHAR_INTR_RE.finditer(text):
            io_to_char.setdefault(m.group(2), m.group(1))
        for m in CHAT_RE.finditer(text):
            chat_to_char.setdefault(m.group(2), m.group(1))

    return io_to_char, chat_to_char


def _extract_call_str(node):
    if isinstance(node, ast.Call) and node.args:
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _walk_chat_items(items, inherited_sender, out):
    """CHOICES entries have no SENDER of their own - they inherit the parent's."""
    for item in items:
        if not isinstance(item, ast.Dict):
            continue
        fields = {_node_to_str(k): v for k, v in zip(item.keys, item.values) if k is not None}

        sender_node = fields.get("SENDER")
        sender = _node_to_str(sender_node) if sender_node is not None else inherited_sender

        content_node = fields.get("CONTENT")
        if content_node is not None:
            text = _extract_call_str(content_node)
            if text:
                extras = [f"{k}={_node_to_str(v)}" for k, v in fields.items()
                          if k not in ("SENDER", "CONTENT", "TYPE", "CHOICES")]
                hint = f"sender: {sender or '?'}"
                if extras:
                    hint += " | " + ", ".join(extras)
                out.setdefault(text, hint)

        choices_node = fields.get("CHOICES")
        if isinstance(choices_node, ast.List):
            _walk_chat_items(choices_node.elts, sender, out)


def build_chat_hints(source_root, lines_cache=None):
    """message text -> "sender: X | field=val, ..." for <cat>["key"] = [...] chat lists."""
    if lines_cache is None:
        lines_cache = {}
    text_hints = {}

    for path in _iter_rpy_files(source_root):
        lines = _read_lines(path, lines_cache)
        if not lines:
            continue

        i = 0
        while i < len(lines):
            if not CHAT_CATALOGUE_ASSIGN_RE.match(lines[i]):
                i += 1
                continue

            chunk, i = _collect_bracketed_chunk(lines, i)
            rhs = "".join(chunk).split('=', 1)[1]
            try:
                tree = ast.parse(rhs.strip(), mode='eval')
            except SyntaxError:
                continue
            if isinstance(tree.body, ast.List):
                _walk_chat_items(tree.body.elts, None, text_hints)

    return text_hints


# sm_quest_list = {...}  (first definition)  /  sm_quest_list.update({...})  (later files)
QUEST_LIST_RE = re.compile(r'^\s*sm_quest_list(?:\s*=\s*\{|\.update\(\{)\s*$')
VN_MODE_DATA_RE = re.compile(r'^\s*VN_MODE_DATA\s*=\s*\{\s*$')


def _collect_translatable_strings(node, out):
    """Recursively pulls every `_("...")` literal out of an entry's value -
    handles a plain string field, a dict of variants, and a
    ("id", [...]) tuple-of-variants form, all the same way."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == '_' and node.args:
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            out.append(arg.value)
        return
    if isinstance(node, ast.Dict):
        for v in node.values:
            _collect_translatable_strings(v, out)
    elif isinstance(node, (ast.List, ast.Tuple)):
        for e in node.elts:
            _collect_translatable_strings(e, out)


def _has_translatable(node):
    """True if this field's own value contains a `_("...")` anywhere - used to
    keep it out of the conditions summary, since it's already shown as the
    translated line itself (a field can hold text without being called HINT
    or NAME specifically, e.g. TRANSITION_TEXT)."""
    found = []
    _collect_translatable_strings(node, found)
    return bool(found)


def build_dict_text_hints(source_root, lines_cache, assign_re, id_label):
    """
    Text -> "<id_label>: <key> | FIELD=val, ...", for any `NAME = {"key": {...},
    ...}` (or `NAME.update({...})`) dict-of-dicts. Entries in these catalogues
    are frequently a single line with no dict-key-opener to anchor on the way
    interaction_*_options.rpy has, so this matches by the literal string text
    instead - same idea as build_chat_hints.
    """
    text_hints = {}

    for path in _iter_rpy_files(source_root):
        lines = _read_lines(path, lines_cache)
        if not lines:
            continue

        i = 0
        while i < len(lines):
            if not assign_re.match(lines[i]):
                i += 1
                continue

            chunk, i = _collect_bracketed_chunk(lines, i)
            text = "".join(chunk)
            try:
                rhs = text[text.index('{'):text.rindex('}') + 1]
                tree = ast.parse(rhs, mode='eval')
            except (ValueError, SyntaxError):
                continue
            if not isinstance(tree.body, ast.Dict):
                continue

            for k, v in zip(tree.body.keys, tree.body.values):
                if k is None or not isinstance(v, ast.Dict):
                    continue
                entry_id = _node_to_str(k)
                extras = [f"{_node_to_str(fk)}={_node_to_str(fv)}" for fk, fv in zip(v.keys, v.values)
                          if fk is not None and not _has_translatable(fv)]
                conditions = f"{id_label}: {entry_id}"
                if extras:
                    conditions += " | " + ", ".join(extras)

                strings = []
                _collect_translatable_strings(v, strings)
                for s in strings:
                    text_hints.setdefault(s, conditions)

    return text_hints


def build_quest_hints(source_root, lines_cache=None):
    if lines_cache is None:
        lines_cache = {}
    return build_dict_text_hints(source_root, lines_cache, QUEST_LIST_RE, "quest")


def build_vn_mode_hints(source_root, lines_cache=None):
    if lines_cache is None:
        lines_cache = {}
    return build_dict_text_hints(source_root, lines_cache, VN_MODE_DATA_RE, "scene")


def _merge_text_hints(*sources):
    """
    The same string can legitimately show up in more than one catalogue (e.g. a
    quest's HINT text matching the NAME of the scene it points to) - combine
    both instead of letting whichever source runs last silently win.
    """
    merged = {}
    for src in sources:
        for text, hint in src.items():
            if text not in merged:
                merged[text] = hint
            elif hint not in merged[text]:
                merged[text] = f"{merged[text]} || {hint}"
    return merged


def build_hints(source_root, lines_cache=None):
    conditions = build_catalogue_conditions(source_root, lines_cache)
    io_to_char, chat_to_char = build_character_index(source_root, lines_cache)
    characters = {**io_to_char, **chat_to_char}
    text_hints = _merge_text_hints(
        build_chat_hints(source_root, lines_cache),
        build_quest_hints(source_root, lines_cache),
        build_vn_mode_hints(source_root, lines_cache),
    )
    return conditions, characters, text_hints