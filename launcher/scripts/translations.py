"""The launcher's translations (Core/Lang/<code>.json, Core/Tr.cs): every English text the window shows, taken from the sources
(Tr.T, Tr.F, Tr.P and Tr.N in App/ and Core/, {c:T '...'} in the .axaml views, and the game's language names in
Core/Languages.cs), checked against each catalog.

    python -I scripts/translations.py                 what each catalog lacks or has left over; exit 1 on either
    python -I scripts/translations.py --missing de    the texts de.json lacks, as JSON to fill in

A catalog maps the English to its translation; a count's entry (Tr.P, keyed by its English "other" form) maps each of the
language's CLDR plural categories to its form. A regional catalog (en-GB, fr-CA, es-419) holds only what differs from its
language's (fr, es) or from English; the others hold every text. Keys starting with @ are notes, not texts.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANG = ROOT / "Core" / "Lang"
REGIONAL = {"en-GB", "fr-CA", "es-419"}
CALL = re.compile(r"\bTr\.([TFPN])\(")
XAML = re.compile(r"\{c:T '((?:[^'\\]|\\.)*)'\}")
PLACEHOLDER = re.compile(r"\{(\d+)(?:[,:][^}]*)?\}")


def plural_categories(code):
    """Core/Tr.cs's PluralCategories"""
    language = code.split("-")[0]
    if language in ("ja", "ko", "zh"):
        return ["other"]
    if language in ("ru", "pl"):
        return ["one", "few", "many", "other"]
    if language in ("fr", "pt", "es", "it"):
        return ["one", "many", "other"]
    return ["one", "other"]


def one_number(code, category):
    """Whether a plural category holds the count 1 alone (Core/Tr.cs's PluralOf), so its form may write the 1 out: fr and
    pt's one is 0 and 1 too, ru's 21, 31...; every other category holds many counts and must show {0}"""
    return category == "one" and code.split("-")[0] not in ("fr", "pt", "ru")


def _string(src, i):
    """The C# string literal at src[i] ("..." or @"..."): its text and the index after it"""
    verbatim = src[i] == "@"
    if verbatim:
        i += 1
    assert src[i] == '"'
    i += 1
    out = []
    while True:
        c = src[i]
        if verbatim:
            if c == '"':
                if src[i + 1:i + 2] == '"':
                    out.append('"')
                    i += 2
                    continue
                return "".join(out), i + 1
            out.append(c)
            i += 1
            continue
        if c == "\\":
            n = src[i + 1]
            if n == "u":
                out.append(chr(int(src[i + 2:i + 6], 16)))
                i += 6
                continue
            out.append({"n": "\n", "t": "\t", "r": "\r", "0": "\0"}.get(n, n))
            i += 2
            continue
        if c == '"':
            return "".join(out), i + 1
        out.append(c)
        i += 1


def _arguments(src, i):
    """The arguments of the call whose ( is just before src[i], each as a list of tokens: ("s", text) for a string literal,
    ("$", None) for an interpolated one, ("+", None), ("x", None) for anything else"""
    args, tokens, depth = [], [], 0
    while i < len(src):
        c = src[i]
        if c == '"' or (c == "@" and src[i + 1:i + 2] == '"'):
            text, i = _string(src, i)
            tokens.append(("s", text))
            continue
        if c == "$" and src[i + 1:i + 2] in ('"', "@"):
            _, i = _string(src, i + 1)
            tokens.append(("$", None))
            continue
        if c == "'":
            j = src.index("'", i + 2 if src[i + 1] == "\\" else i + 1)
            i = j + 1
            tokens.append(("x", None))
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            if depth == 0:
                args.append(tokens)
                return args
            depth -= 1
        elif c == "," and depth == 0:
            args.append(tokens)
            tokens = []
            i += 1
            continue
        if c == "+" and depth == 0:
            tokens.append(("+", None))
        elif not c.isspace() and depth == 0 and tokens[-1:] != [("x", None)]:
            tokens.append(("x", None))
        i += 1
    raise ValueError("unclosed call")


def _texts(tokens):
    """The English texts an argument can be: each run of string literals joined by +"""
    texts, run, joined = [], None, False
    for kind, value in tokens:
        if kind == "s":
            run = value if run is None or not joined else run + value
            joined = False
        elif kind == "+":
            joined = run is not None
        else:
            if run is not None:
                texts.append(run)
            run, joined = None, False
    if run is not None:
        texts.append(run)
    return texts


def sources():
    """Every English text the window can show: {text: plural's English "one" form or None}, and the faults found"""
    texts, faults = {}, []
    files = [p for p in sorted((ROOT / "App").rglob("*.cs")) + sorted((ROOT / "Core").rglob("*.cs"))
             if "obj" not in p.parts and "bin" not in p.parts and p.name != "Tr.cs"]
    for path in files:
        src = path.read_text(encoding="utf-8")
        for m in CALL.finditer(src):
            line = src.count("\n", 0, m.start()) + 1
            args = _arguments(src, m.end())
            where = "%s:%d" % (path.relative_to(ROOT).as_posix(), line)
            english = args[1:3] if m.group(1) == "P" else args[:1]
            if any(("$", None) in a for a in english):
                faults.append("%s: an interpolated string ($\"...\") in Tr.%s: its English is not one text" % (where, m.group(1)))
            if m.group(1) == "P":
                ones, others = _texts(args[1]), _texts(args[2]) if len(args) > 2 else []
                if len(ones) != len(others):
                    faults.append("%s: Tr.P's one and other forms do not pair up" % where)
                for one, other in zip(ones, others):
                    texts[other] = one
            else:
                for t in _texts(args[0]):
                    texts.setdefault(t, None)
    for path in sorted((ROOT / "App").rglob("*.axaml")):
        if "obj" in path.parts:
            continue
        for m in XAML.finditer(path.read_text(encoding="utf-8")):
            text = re.sub(r"\\(.)", r"\1", m.group(1))
            texts.setdefault(html.unescape(text), None)
    languages = (ROOT / "Core" / "Languages.cs").read_text(encoding="utf-8")
    body = languages[languages.index("All = new[]"):languages.index("};", languages.index("All = new[]"))]
    for _, name in re.findall(r'\("([^"]+)", "([^"]+)"\)', body):
        texts.setdefault(name, None)
    return texts, faults


def _places(text):
    return {int(n) for n in PLACEHOLDER.findall(text)}


def _bad_braces(text):
    """A text string.Format would refuse: a lone { or } outside a placeholder"""
    rest = PLACEHOLDER.sub("", text.replace("{{", "").replace("}}", ""))
    return "{" in rest or "}" in rest


def codes():
    tr = (ROOT / "Core" / "Tr.cs").read_text(encoding="utf-8")
    body = tr[tr.index("All = new[]"):tr.index("};", tr.index("All = new[]"))]
    return [c for c, _ in re.findall(r'\("([^"]+)", "([^"]+)"\)', body)]


def check():
    """The faults of the sources and of every catalog, and what each lacks"""
    texts, faults = sources()
    lacking = {}
    for code in codes():
        if code == "en-US":
            continue
        path = LANG / (code + ".json")
        if not path.is_file():
            faults.append("Core/Lang/%s.json is missing" % code)
            if code not in REGIONAL:
                lacking[code] = list(texts)
            continue
        try:
            catalog = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            faults.append("Core/Lang/%s.json: %s" % (code, e))
            continue
        name = "Core/Lang/%s.json" % code
        for key, value in catalog.items():
            if key.startswith("@"):
                continue
            if key not in texts:
                faults.append("%s: %r is no text of the launcher's (left over?)" % (name, key))
                continue
            plural = texts[key] is not None
            if plural != isinstance(value, dict):
                faults.append("%s: %r must be %s" % (name, key, "an object of plural forms" if plural else "a string"))
                continue
            want = _places(key)
            forms = value.items() if plural else [("", value)]
            if plural:
                need = plural_categories(code)
                missing = [c for c in need if c not in value]
                extra = [c for c in value if c not in need]
                if missing or extra:
                    faults.append("%s: %r's forms are %s; %s takes %s" % (name, key, sorted(value), code, need))
            for category, text in forms:
                if not isinstance(text, str):
                    faults.append("%s: %r %s is not a string" % (name, key, category))
                    continue
                have = _places(text)
                ok = have <= want | {0} if plural else have == want
                if not ok:
                    faults.append("%s: %r %s has placeholders %s, the English %s" % (name, key, category, sorted(have), sorted(want)))
                elif plural and 0 not in have and not one_number(code, category):
                    faults.append("%s: %r %s does not show the count ({0}): %s's %s holds more than one number"
                                  % (name, key, category, code, category))
                if _bad_braces(text):
                    faults.append("%s: %r %s has a lone brace (write {{ or }})" % (name, key, category))
        if code not in REGIONAL:
            lacking[code] = [t for t in texts if t not in catalog]
    return texts, faults, lacking


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--missing", metavar="CODE", help="print the texts this catalog lacks, as JSON")
    args = parser.parse_args()
    texts, faults, lacking = check()
    if args.missing:
        cats = plural_categories(args.missing)
        out = {t: ({c: (one if c == "one" else t) for c in cats} if one is not None else t)
               for t, one in texts.items() if t in lacking.get(args.missing, [])}
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    for f in faults:
        print(f)
    for code, missing in lacking.items():
        if missing:
            print("Core/Lang/%s.json lacks %d of %d texts (--missing %s lists them)" % (code, len(missing), len(texts), code))
    if not faults and not any(lacking.values()):
        print("translations: %d texts, %d catalogs, all complete" % (len(texts), len(codes()) - 1))
    return 1 if faults or any(lacking.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
