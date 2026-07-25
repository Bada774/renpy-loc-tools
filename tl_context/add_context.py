import argparse
import importlib
import os
import re
import sys

# Ren'Py always writes source refs as "game/..." regardless of how the project
# is actually laid out on disk, so this gets stripped before joining with
# whatever source_root actually is for this run.
GAME_REF_PREFIX = "game/"

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GAME_SCRIPTS_ROOT = os.path.join(_SCRIPT_DIR, "GameSpecificScripts")

LABEL_RE = re.compile(r'^\s*label\s+([A-Za-z_]\w*)\s*:')
JUMP_RE = re.compile(r'^\s*jump\s+([A-Za-z_]\w*)\s*$')  # static jumps only, no `jump expression`

DELIM_RE = re.compile(r'^\s*#\s*=+\s*$')
GAME_REF_RE = re.compile(r'^(\s*)#\s+(game/.*\.rpy):(\d+)')
# Ren'Py drops one of these comments wherever it appended freshly
# changed/new content on a translation update. What immediately follows it
# varies by file layout (a shared "translate LANG strings:" header in some,
# a ref line directly in others), so the comment itself - not whatever's
# after it - is the reset point for dedup.
TODO_FIXME_RE = re.compile(r'^\s*#\s*(?:\[.\]\s*)?(TODO|FIXME):', re.IGNORECASE)

DICT_KEY_OPEN_RE = re.compile(r'^(?:"([^"]+)"|\'([^\']+)\'|([A-Za-z_]\w*))\s*:\s*[\{\[]\s*$')
BRACKET_ASSIGN_RE = re.compile(r'\[\s*["\']([^"\']+)["\']\s*\]\s*=\s*[\{\[]\s*$')


def load_optional_module(module_dir, name):
    if not module_dir or not os.path.isdir(module_dir):
        return None
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    try:
        return importlib.import_module(name)
    except ImportError:
        return None


def load_game_hints(game_code):
    module_dir = os.path.join(GAME_SCRIPTS_ROOT, game_code)
    return load_optional_module(module_dir, "game_hints"), module_dir


def resolve_game(path_to_check, explicit_game):
    """
    Explicit -g always wins. Otherwise try to auto-detect from each game's
    config.py: PROJECT_MARKERS is a list of substrings, and if exactly one
    game's marker matches path_to_check, that's the game. Ambiguous or no
    match -> None, caller has to ask for -g.
    """
    if explicit_game:
        return explicit_game

    available = sorted(os.listdir(GAME_SCRIPTS_ROOT)) if os.path.isdir(GAME_SCRIPTS_ROOT) else []
    norm_path = os.path.normcase(os.path.abspath(path_to_check))

    matches = []
    for code in available:
        config = load_optional_module(os.path.join(GAME_SCRIPTS_ROOT, code), "config")
        markers = getattr(config, "PROJECT_MARKERS", None) if config else None
        if markers and any(os.path.normcase(m) in norm_path for m in markers):
            matches.append(code)

    if len(matches) == 1:
        print(f"  auto-detected game: {matches[0]}")
        return matches[0]

    if len(matches) > 1:
        print(f"error: '{path_to_check}' matches PROJECT_MARKERS for multiple games "
              f"({', '.join(matches)}) - pass -g to disambiguate")
    else:
        print(f"error: no -g given and no config.py PROJECT_MARKERS matched '{path_to_check}'. "
              f"available: {', '.join(available) or 'none'}")
    return None


def _extract_anchor_key(stripped_line):
    """Dict key opener (`"io-xxx": {`) or indexed assignment (`CAT["x"] = [`) -> the key."""
    m = DICT_KEY_OPEN_RE.match(stripped_line)
    if m:
        return m.group(1) or m.group(2) or m.group(3)
    m = BRACKET_ASSIGN_RE.search(stripped_line)
    if m:
        return m.group(1)
    return None


def _read_lines(filepath, cache):
    if filepath not in cache:
        if not os.path.exists(filepath):
            cache[filepath] = None
        else:
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                cache[filepath] = f.readlines()
    return cache[filepath]


def find_matching_if(lines, start_idx, target_indent):
    for i in range(start_idx - 1, -1, -1):
        line = lines[i]
        stripped = line.strip()
        indent = len(line) - len(stripped)
        if not stripped or stripped.startswith('#'):
            continue
        if indent == target_indent:
            if stripped.startswith('if '):
                return stripped
        elif indent < target_indent:
            break
    return None


def _build_raw_context_stack(lines, target_idx):
    """Walk upward from target_idx collecting enclosing blocks. Stops at label/init."""
    if lines is None or target_idx >= len(lines) or target_idx < 0:
        return [], None

    target_line = lines[target_idx]
    target_indent = len(target_line) - len(target_line.lstrip())

    context_stack = []
    current_indent = target_indent
    stopped_label = None

    for i in range(target_idx - 1, -1, -1):
        line = lines[i]
        stripped = line.strip()
        indent = len(line) - len(stripped)

        if not stripped or stripped.startswith('#'):
            continue

        if indent < current_indent:
            is_block = stripped.endswith((':', '{', '['))
            is_assign = bool(re.match(r'^[A-Za-z0-9_\[\]\"\'\-\s]+\s*=(?!=)', stripped))

            if is_block or is_assign:
                block_text = stripped

                if stripped.startswith('else:') or stripped.startswith('elif '):
                    if_text = find_matching_if(lines, i, indent)
                    if if_text:
                        block_text = f"{if_text} -> {stripped}"

                context_stack.append(block_text)
                current_indent = indent

                if stripped.startswith('label '):
                    m = LABEL_RE.match(line)
                    stopped_label = m.group(1) if m else None
                    break
                if stripped.startswith('init '):
                    break

    context_stack.reverse()
    return context_stack, stopped_label


def build_jump_index(source_root):
    """label -> list of places that `jump` into it, each with its own context."""
    rpy_files = []
    for root, dirs, files in os.walk(source_root):
        dirs[:] = [d for d in dirs if d != 'tl']
        for f in files:
            if f.endswith(".rpy"):
                rpy_files.append(os.path.join(root, f))

    lines_cache = {}
    jump_sources = {}
    for path in rpy_files:
        lines = _read_lines(path, lines_cache)
        if not lines:
            continue
        for i, line in enumerate(lines):
            m = JUMP_RE.match(line.strip())
            if not m:
                continue
            target = m.group(1)
            raw_stack, from_label = _build_raw_context_stack(lines, i)
            jump_sources.setdefault(target, []).append({"context": raw_stack, "from_label": from_label})

    return jump_sources, lines_cache


def _predecessor_segments(label, jump_sources, visited, depth=0, max_depth=5):
    """
    Walk the jump chain leading into `label`. Returns (segments, warning).
    If more than one place jumps here, we don't guess which one — just warn.
    """
    if depth >= max_depth or label not in jump_sources or label in visited:
        return [], None

    predecessors = jump_sources[label]
    if len(predecessors) != 1:
        names = sorted({p["from_label"] or "?" for p in predecessors})
        shown = ", ".join(names[:4])
        more = f" (+{len(names) - 4})" if len(names) > 4 else ""
        return [], f"warning: multiple jumps lead here: {shown}{more}"

    pred = predecessors[0]
    visited = visited | {label}

    upstream_segments, upstream_warning = [], None
    if pred["from_label"]:
        upstream_segments, upstream_warning = _predecessor_segments(
            pred["from_label"], jump_sources, visited, depth + 1, max_depth
        )

    if not pred["context"]:
        return upstream_segments, upstream_warning

    this_segment = list(pred["context"]) + [f"jump {label}"]
    return upstream_segments + [this_segment], upstream_warning


def _format_segments(segments):
    lines = []
    for seg in segments:
        for i, item in enumerate(seg):
            if i == 0:
                lines.append(f"# @ {item}")
            else:
                lines.append(f"#{'    ' * i}↳ {item}")
    return lines


def _unquote(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    return s


def get_context_from_original(filepath, fallback_line_num, search_text=None,
                               jump_sources=None, conditions=None, characters=None,
                               text_hints=None, text_key=None, lines_cache=None):
    if lines_cache is None:
        lines_cache = {}

    lines = _read_lines(filepath, lines_cache)
    if not lines:
        return None

    target_idx = fallback_line_num - 1

    # Line numbers drift between decompiled source and the translation file (and
    # for strings extracted from python `_("...")` calls, Ren'Py often just gives
    # the same fixed line for a whole block regardless of where the string
    # actually is) - if the exact phrase isn't on fallback_line_num, take the
    # closest occurrence anywhere in the file instead.
    if search_text:
        closest_i, min_dist = -1, float('inf')
        for i, line in enumerate(lines):
            if search_text in line:
                dist = abs(i - target_idx)
                if dist < min_dist:
                    min_dist, closest_i = dist, i
        if closest_i != -1:
            target_idx = closest_i

    raw_stack, stopped_label = _build_raw_context_stack(lines, target_idx)
    if not raw_stack:
        return None

    pred_segments, warning = [], None
    if jump_sources and stopped_label:
        pred_segments, warning = _predecessor_segments(stopped_label, jump_sources, set())

    formatted_pred = _format_segments(pred_segments)
    formatted_own = _format_segments([raw_stack])

    # Hints belong to the innermost container, not the jump ancestors, so they go
    # right above formatted_own. Look up by label first, then by whatever key the
    # nearest dict/list opener has (catalogue entries, chat blocks, etc).
    immediate_key = _extract_anchor_key(raw_stack[-1]) if raw_stack else None
    lookup_keys = [k for k in (stopped_label, immediate_key) if k]

    hint_parts = []
    for key in lookup_keys:
        if characters and key in characters and not any(p.startswith("character") for p in hint_parts):
            hint_parts.append(f"character: {characters[key]}")
        if conditions and key in conditions and not any(p.startswith("conditions") for p in hint_parts):
            hint_parts.append(f"conditions: {conditions[key]}")

    # Chat messages are anonymous dicts in a list, no key to anchor on, so this
    # one's matched by the line's own text instead.
    if text_hints and text_key and text_key in text_hints:
        hint_parts.append(text_hints[text_key])

    if hint_parts:
        formatted_own.insert(0, f"# ! {' | '.join(hint_parts)}")

    formatted = formatted_pred + formatted_own
    if warning:
        formatted.insert(0, f"# {warning}")

    return formatted if formatted else None


def process_translation_file(tl_filepath, jump_sources, conditions, characters, text_hints,
                              lines_cache, source_root):
    with open(tl_filepath, 'r', encoding='utf-8-sig') as f:
        original_lines = f.readlines()

    new_lines = []
    last_context_blocks = None
    total_refs = 0
    missing_source = 0

    i, n = 0, len(original_lines)
    while i < n:
        line = original_lines[i]

        if TODO_FIXME_RE.match(line):
            last_context_blocks = None
            new_lines.append(line)
            i += 1
            continue

        # An existing block of ours is DELIM ... DELIM immediately followed by a
        # ref line. Detect it and hold onto it - if we can't rebuild a fresh block
        # for that ref below, we put this one back rather than just dropping it.
        old_block = None
        if DELIM_RE.match(line):
            j = i + 1
            comments_only = True
            while j < n and not DELIM_RE.match(original_lines[j]):
                if original_lines[j].strip() and not original_lines[j].lstrip().startswith('#'):
                    comments_only = False
                    break
                j += 1
            closed = comments_only and j < n and DELIM_RE.match(original_lines[j])
            if closed and j + 1 < n and GAME_REF_RE.match(original_lines[j + 1]):
                old_block = original_lines[i:j + 1]
                i = j + 1
                line = original_lines[i]

        match = GAME_REF_RE.match(line)
        if match:
            total_refs += 1
            indent_str = match.group(1)
            ref_path = match.group(2)
            rel_path = ref_path[len(GAME_REF_PREFIX):] if ref_path.startswith(GAME_REF_PREFIX) else ref_path
            orig_filepath = os.path.join(source_root, rel_path)
            fallback_line_num = int(match.group(3))

            search_text = None
            text_key = None
            for lookahead in range(1, 6):
                if i + lookahead < n:
                    la_line = original_lines[i + lookahead].strip()
                    if la_line.startswith('#') and '"' in la_line and not la_line.startswith('# game/'):
                        search_text = la_line[1:].strip()
                        break
                    elif la_line.startswith('old "'):
                        search_text = la_line[4:].strip()
                        text_key = _unquote(search_text)
                        break

            # Two different reasons context_blocks can come back empty: the source
            # file itself doesn't exist at this path (a real --source problem), or
            # the file's there but this particular line just isn't inside any
            # label/dict (e.g. a flat `define NAME = _("...")` constants file -
            # nothing wrong, there's simply no enclosing context to report).
            source_exists = _read_lines(orig_filepath, lines_cache) is not None
            context_blocks = get_context_from_original(
                orig_filepath, fallback_line_num, search_text,
                jump_sources=jump_sources, conditions=conditions, characters=characters,
                text_hints=text_hints, text_key=text_key, lines_cache=lines_cache,
            )

            if context_blocks:
                if context_blocks != last_context_blocks:
                    new_lines.append(indent_str + "# " + "=" * 50 + "\n")
                    for block in context_blocks:
                        new_lines.append(indent_str + block + "\n")
                    new_lines.append(indent_str + "# " + "=" * 50 + "\n")
                    last_context_blocks = context_blocks
            elif old_block:
                # Couldn't rebuild it this time - keep what was already there
                # instead of deleting it, whichever of the two reasons above caused it.
                # Deliberately not touching last_context_blocks: a single line we
                # can't resolve (stale "old" text, no enclosing context, etc.)
                # shouldn't break the dedup chain for everything after it.
                if not source_exists:
                    missing_source += 1
                new_lines.extend(old_block)
            else:
                if not source_exists:
                    missing_source += 1
                # A single ref with nothing to show (bad text match, no enclosing
                # block, whatever) doesn't mean the surrounding context changed -
                # don't reset last_context_blocks, or the next ref that resolves
                # back to the same context re-inserts a duplicate header.

        new_lines.append(line)
        i += 1

    if missing_source:
        print(f"  {tl_filepath}: {missing_source}/{total_refs} refs point to a source file "
              f"that couldn't be found under source_root={source_root} - check --source path")

    if original_lines != new_lines:
        with open(tl_filepath, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        print(f"updated: {tl_filepath}")

    return total_refs, missing_source


def resolve_language_dirs(tl_root, lang_arg, config):
    """
    Default: no restriction - walk everything under tl_root, whatever languages
    happen to be there. --lang or config.py's LANGUAGES narrows that down to
    specific subfolders. --lang always wins over the config.
    """
    if not os.path.isdir(tl_root):
        return []

    names = None
    if lang_arg and lang_arg != "all":
        names = [n.strip() for n in lang_arg.split(",") if n.strip()]
    elif not lang_arg:
        cfg_languages = getattr(config, "LANGUAGES", None) if config else None
        if cfg_languages:
            names = list(cfg_languages)

    if names is None:
        return [tl_root]
    return [os.path.join(tl_root, name) for name in names]


def run_project(source_root, tl_root, game_code, lang_arg):
    print(f"\n=== source: {source_root} ===")

    game_hints, module_dir = load_game_hints(game_code)
    config = load_optional_module(module_dir, "config")

    print("indexing jumps...")
    jump_sources, lines_cache = build_jump_index(source_root)
    print(f"  labels with incoming jumps: {len(jump_sources)}")

    conditions, characters, text_hints = {}, {}, {}
    if game_hints is not None:
        conditions, characters, text_hints = game_hints.build_hints(source_root, lines_cache)
        print(f"  game_hints: {len(conditions)} conditions, {len(characters)} character mappings, "
              f"{len(text_hints)} chat messages")
    else:
        available = sorted(os.listdir(GAME_SCRIPTS_ROOT)) if os.path.isdir(GAME_SCRIPTS_ROOT) else []
        print(f"  no game_hints.py for '{game_code}' ({module_dir}) — condition/character/chat hints "
              f"skipped. available: {', '.join(available) or 'none'}")

    for tl_dir in resolve_language_dirs(tl_root, lang_arg, config):
        if not os.path.isdir(tl_dir):
            print(f"  skip (not found): {tl_dir}")
            continue
        print(f"  tl: {tl_dir}")
        total_refs, missing_source = 0, 0
        for root, _, files in os.walk(tl_dir):
            for f in files:
                if f.endswith(".rpy"):
                    refs, missed = process_translation_file(
                        os.path.join(root, f), jump_sources, conditions, characters,
                        text_hints, lines_cache, source_root,
                    )
                    total_refs += refs
                    missing_source += missed
        if total_refs and missing_source == total_refs:
            print(f"  WARNING: none of {total_refs} refs resolved against source_root={source_root} "
                  f"- --source is almost certainly wrong")
        elif missing_source:
            print(f"  {missing_source}/{total_refs} refs across {tl_dir} point to a missing source file")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Adds breadcrumb context (label/jump/conditions/sender) to Ren'Py translation files."
    )
    parser.add_argument(
        "game_dir", nargs="?", default="game",
        help="Path to the game/ folder itself (source_root=game_dir, tl_root=game_dir/tl). "
             "Only used when --source/--tl aren't given. Default: game",
    )
    parser.add_argument(
        "-g", "--game", action="append", default=None,
        help="Game code (subfolder of GameSpecificScripts). Repeat to pair with multiple "
             "--source/--tl, or pass once to apply to all. If omitted, tries to auto-detect "
             "from each game's config.py (PROJECT_MARKERS) - errors out if that's ambiguous.",
    )
    parser.add_argument(
        "--source", "--code", dest="source", action="append", default=None,
        help="Path to the game's source. Repeatable for multiple projects in one run.",
    )
    parser.add_argument(
        "--tl", "--translation", dest="tl", action="append", default=None,
        help="Path to the tl/ root. Without --lang, every language folder under it is "
             "processed (or whatever config.py's LANGUAGES restricts it to).",
    )
    parser.add_argument(
        "--lang", default=None,
        help="Comma-separated language folder names under tl/ (e.g. russian,french) - "
             "overrides config.py's LANGUAGES. Omit to use the config, or every language "
             "found if the config doesn't set one either.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.source or args.tl:
        sources, tls = args.source or [], args.tl or []
        if len(sources) != len(tls):
            print("error: --source and --tl must be given the same number of times")
            return

        games = args.game
        if games and len(games) == 1:
            games = games * len(sources)
        elif games and len(games) != len(sources):
            print("error: -g/--game must be given once (applies to all) or once per --source")
            return
        else:
            games = [None] * len(sources)  # auto-detect per project below

        for source, tl, game in zip(sources, tls, games):
            source = os.path.abspath(source)
            resolved = resolve_game(source, game)
            if not resolved:
                continue
            run_project(source, os.path.abspath(tl), resolved, args.lang)
        return

    # No explicit paths -> game_dir directly (source_root=game_dir, tl_root=game_dir/tl).
    game_dir = os.path.abspath(args.game_dir)
    if not os.path.isdir(game_dir):
        print(f"game folder not found: {game_dir}")
        return

    game = (args.game or [None])[0]
    game = resolve_game(game_dir, game)
    if not game:
        return

    run_project(game_dir, os.path.join(game_dir, "tl"), game, args.lang)


if __name__ == "__main__":
    main()