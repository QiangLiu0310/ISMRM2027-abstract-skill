#!/usr/bin/env python3
"""Convert a conference-abstract LaTeX file into the shared page's data/abstract.json.

Usage: python3 tex2json.py abstract.tex out_dir [--limits body=750,synopsis=100,impact=40,caption=500]
                           [--header "ISMRM 2027 · My Abstract"]

Writes out_dir/data/abstract.json and prints the figure files it found (in order) plus
any LaTeX it could not turn into plain text. Those warnings must be fixed by hand in the
JSON before publishing.

Structure it understands:
  - title / authors / affiliations: \\title{} \\author{} or, inside a center block, a
    \\bfseries line, the next line, and a \\footnotesize or \\small line
  - \\section*{Impact...}            -> impact (one paragraph)
  - \\section*{Synopsis...}          -> synopsis items, each "\\para{Label:} text" or "\\textbf{Label:} text"
  - \\section*{References}           -> one reference per line or \\item / \\bibitem
  - \\section*{Figures} and every figure environment -> figures (\\includegraphics + \\caption)
  - any other \\section / \\section*   -> body; one block per paragraph, an optional leading
    \\para{} / \\textbf{} / \\paragraph{} becomes the block label
"""
import json, os, re, sys

SUP = dict(zip("0123456789+-−–(),=n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻⁻⁽⁾˒⁼ⁿ"))
SUB = dict(zip("0123456789+-=()", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎"))
GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "Delta": "Δ", "epsilon": "ε", "varepsilon": "ε",
    "zeta": "ζ", "eta": "η", "theta": "θ", "Theta": "Θ", "kappa": "κ", "lambda": "λ", "Lambda": "Λ", "mu": "μ",
    "nu": "ν", "xi": "ξ", "pi": "π", "Pi": "Π", "rho": "ρ", "sigma": "σ", "Sigma": "Σ", "tau": "τ", "phi": "φ",
    "varphi": "φ", "Phi": "Φ", "chi": "χ", "psi": "ψ", "Psi": "Ψ", "omega": "ω", "Omega": "Ω",
}
SYMBOLS = {
    "times": "×", "cdot": "·", "sim": "~", "approx": "≈", "pm": "±", "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥",
    "neq": "≠", "rightarrow": "→", "to": "→", "leftarrow": "←", "Rightarrow": "⇒", "infty": "∞", "partial": "∂",
    "nabla": "∇", "sum": "Σ", "prod": "Π", "int": "∫", "sqrt": "√", "propto": "∝", "in": "∈", "circ": "°",
    "ell": "ℓ", "max": "max", "min": "min", "log": "log", "exp": "exp", "|": "‖", "{": "{", "}": "}",
    "textdegree": "°", "textmu": "µ", "us": "µs", "%": "%", "&": "&", "_": "_", "#": "#", "$": "$",
    "ldots": "…", "dots": "…", "textendash": "–", "textemdash": "—", "LaTeX": "LaTeX", "S": "§",
}
ACCENT = {"'": "\u0301", "`": "\u0300", '"': "\u0308", "^": "\u0302", "~": "\u0303", "c": "\u0327", "v": "\u030c"}
DROP = ("label", "vspace", "hspace", "noindent", "centering", "par", "small", "footnotesize", "large", "Large",
        "normalsize", "itshape", "bfseries", "clearpage", "newpage", "medskip", "smallskip", "bigskip", "quad", "qquad")

warnings = []


def group(s, i):
    """s[i] == '{' -> (content, index after the matching '}')."""
    depth, j = 0, i
    while j < len(s):
        if s[j] == "\\":
            j += 2
            continue
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    return s[i + 1:], len(s)


def arg(s, i):
    """Read one macro argument starting at s[i] (skipping spaces and [opt])."""
    while i < len(s) and s[i] == " ":
        i += 1
    if i < len(s) and s[i] == "[":
        i = s.index("]", i) + 1
    if i < len(s) and s[i] == "{":
        return group(s, i)
    if i < len(s) and s[i] == "\\":
        m = re.match(r"\\[A-Za-z]+|\\.", s[i:])
        return m.group(0), i + len(m.group(0))
    return (s[i], i + 1) if i < len(s) else ("", i)


def script(text, table, mark):
    if all(c in table for c in text):
        return "".join(table[c] for c in text)
    return mark + (text if len(text) == 1 or text.isalnum() else "{" + text + "}")


def conv(s, math=False):
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "%" and (i == 0 or s[i - 1] != "\\"):
            j = s.find("\n", i)
            i = len(s) if j < 0 else j + 1
            continue
        if c == "$":
            j = s.find("$", i + 1)
            j = len(s) if j < 0 else j
            out.append("$" + re.sub(r"\s+", " ", s[i + 1:j]).strip() + "$")  # the page renders $...$ with MathJax
            i = j + 1
            continue
        if c == "{":
            g, i = group(s, i)
            out.append(conv(g, math))
            continue
        if c == "}":
            i += 1
            continue
        if math and c in "^_":
            a, i = arg(s, i + 1)
            a = conv(a, True)
            out.append(script(a, SUP if c == "^" else SUB, c))
            continue
        if c == "~" and not math:
            out.append(" ")
            i += 1
            continue
        if c == "-" and not math and s.startswith("---", i):
            out.append("—"); i += 3; continue
        if c == "-" and not math and s.startswith("--", i):
            out.append("–"); i += 2; continue
        if c == "`" and s.startswith("``", i):
            out.append("“"); i += 2; continue
        if c == "'" and s.startswith("''", i):
            out.append("”"); i += 2; continue
        if c == "'" and not math:
            out.append("’"); i += 1; continue
        if c == "-" and math:
            out.append("−"); i += 1; continue
        if c == "\\":
            m = re.match(r"\\([A-Za-z]+)\*?|\\(.)", s[i:])
            name = m.group(1) or m.group(2)
            i += len(m.group(0))
            if name in (",", ";", ":", "!", " ", "/"):
                out.append("" if name in ("!", "/") else " ")
            elif name == "\\":
                out.append(" ")
            elif name in ACCENT:
                a, i = arg(s, i)
                out.append(__import__("unicodedata").normalize("NFC", conv(a) + ACCENT[name]))
            elif name in GREEK:
                out.append(GREEK[name])
            elif name in SYMBOLS:
                out.append(SYMBOLS[name])
            elif name == "textsuperscript":
                a, i = arg(s, i)
                out.append(script(conv(a), SUP, "^"))
            elif name == "textsubscript":
                a, i = arg(s, i)
                out.append(script(conv(a), SUB, "_"))
            elif name == "hat":
                a, i = arg(s, i)
                out.append(conv(a, math) + "\u0302")
            elif name == "tilde":
                a, i = arg(s, i)
                out.append(conv(a, math) + "\u0303")
            elif name in ("bar", "overline"):
                a, i = arg(s, i)
                out.append(conv(a, math) + "\u0304")
            elif name == "frac":
                a, i = arg(s, i)
                b, i = arg(s, i)
                out.append(conv(a, True) + "/" + conv(b, True))
            elif name in ("para", "textbf", "textit", "emph", "textrm", "textsf", "texttt", "mathrm", "mathbf", "mathit",
                          "mathcal", "mathbb", "boldsymbol", "text", "mbox", "underline", "operatorname"):
                a, i = arg(s, i)
                out.append(conv(a, math))
            elif name in ("left", "right", "big", "Big", "bigl", "bigr"):
                pass
            elif name in DROP:
                if name in ("vspace", "hspace", "label"):
                    _, i = arg(s, i)
            elif name in ("cite", "ref", "eqref"):
                a, i = arg(s, i)
                out.append("[" + a + "]")
                warnings.append("\\%s{%s} left as [%s]" % (name, a, a))
            else:
                out.append("\\" + name)
                warnings.append("unknown macro \\" + name)
            continue
        out.append(c)
        i += 1
    t = "".join(out)
    t = __import__("unicodedata").normalize("NFC", t)
    return t if math else re.sub(r"\s+", " ", t).strip()


def slug(s, used):
    base = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:24] or "block"
    k, n = base, 2
    while k in used:
        k, n = "%s-%d" % (base, n), n + 1
    used.add(k)
    return k


def lead_label(p):
    m = re.match(r"\s*\\(para|textbf|paragraph\*?)\s*\{", p)
    if not m:
        return "", p
    g, j = group(p, m.end() - 1)
    return conv(g), p[j:]


def main():
    a = sys.argv[1:]
    if len(a) < 2:
        sys.exit(__doc__)
    tex, out_dir = a[0], a[1]
    limits, header = {}, None
    if "--limits" in a:
        for kv in a[a.index("--limits") + 1].split(","):
            k, v = kv.split("=")
            limits[k.strip()] = int(v)
    if "--header" in a:
        header = a[a.index("--header") + 1]
    src = open(tex, encoding="utf-8").read()
    src = re.sub(r"(?<!\\)%.*", "", src)
    body_src = src.split("\\begin{document}", 1)[-1].split("\\end{document}", 1)[0]

    d = {"title": "", "authors": "", "affiliations": ""}
    m = re.search(r"\\title\s*\{", src)
    if m:
        d["title"] = conv(group(src, m.end() - 1)[0])
        m2 = re.search(r"\\author\s*\{", src)
        if m2:
            d["authors"] = conv(group(src, m2.end() - 1)[0])
    else:
        cm = re.search(r"\\begin\{center\}(.*?)\\end\{center\}", body_src, re.S)
        if cm:
            lines = [l for l in cm.group(1).split("\n") if l.strip() and not re.match(r"\s*\\vspace", l)]
            if lines:
                d["title"] = conv(lines[0])
            rest = lines[1:]
            for l in rest:
                if re.search(r"\\(footnotesize|small|scriptsize)", l):
                    d["affiliations"] = conv(l)
                elif not d["authors"]:
                    d["authors"] = conv(l)

    used, figures = set(), []
    for fm in re.finditer(r"\\begin\{figure\*?\}(.*?)\\end\{figure\*?\}", body_src, re.S):
        f = fm.group(1)
        im = re.search(r"\\includegraphics\s*(\[[^\]]*\])?\s*\{([^}]*)\}", f)
        cm = re.search(r"\\caption\s*\{", f)
        cap = conv(group(f, cm.end() - 1)[0]) if cm else ""
        figures.append({"id": "cap%d" % (len(figures) + 1), "file": "fig/fig%d.jpg" % (len(figures) + 1),
                        "text": cap, "_source": im.group(2) if im else ""})
    body_src = re.sub(r"\\begin\{figure\*?\}.*?\\end\{figure\*?\}", "", body_src, flags=re.S)

    synopsis, body, refs = [], [], []
    parts = re.split(r"\\section\*?\s*\{([^}]*)\}", body_src)
    for k in range(1, len(parts), 2):
        name, text = parts[k].strip(), parts[k + 1]
        key = name.lower()
        paras = [p for p in re.split(r"\n\s*\n", text) if conv(p)]
        if key.startswith("impact"):
            d["impact"] = conv(" ".join(paras))
        elif key.startswith("synopsis"):
            for p in paras:
                lab, rest = lead_label(p)
                synopsis.append({"id": slug("syn-" + (lab or "item"), used), "label": lab, "text": conv(rest)})
        elif key.startswith("reference") or key.startswith("bibliograph"):
            items = re.split(r"\\par\b|\\item\b|\\bibitem\{[^}]*\}|\n", text)
            for it in items:
                t = re.sub(r"^\s*\d+[.)]\s*", "", conv(it))
                if t and not t.startswith("{") and len(t) > 3:
                    refs.append({"id": "ref%d" % (len(refs) + 1), "text": t})
        elif key.startswith("figure"):
            continue
        else:
            sec = re.sub(r"\s*\(.*?\)\s*$", "", name)
            for p in paras:
                lab, rest = lead_label(p)
                body.append({"id": slug((sec[:10] + "-" + (lab or str(len(body) + 1))), used),
                             "section": sec, "label": lab, "text": conv(rest)})
    if synopsis:
        d["synopsis"] = synopsis
    d["body"], d["figures"], d["references"] = body, [{k: v for k, v in f.items() if k != "_source"} for f in figures], refs
    if limits:
        d["limits"] = limits
    if header:
        d["header"] = header
    d["history"] = []

    os.makedirs(os.path.join(out_dir, "data"), exist_ok=True)
    with open(os.path.join(out_dir, "data", "abstract.json"), "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, indent=1)
    print("wrote", os.path.join(out_dir, "data", "abstract.json"))
    print("blocks: body %d, synopsis %d, figures %d, references %d" % (len(body), len(synopsis), len(figures), len(refs)))
    print("figure sources (in order):")
    for f in figures:
        print("  %s <- %s" % (f["file"], f["_source"]))
    for w in sorted(set(warnings)):
        print("WARNING:", w)


if __name__ == "__main__":
    main()
