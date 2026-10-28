#!/usr/bin/env python3
"""List what co-authors changed on the shared page since the last sync.

Usage: python3 sync_edits.py baseline.json live.json [--accept]

baseline.json  the local shared_page/data/abstract.json (the state last synced into LaTeX)
live.json      data/abstract.json just pulled from the published artifact

Prints every changed field with its old and new text, a word-level diff, and the history
entries (who/when) behind it. Claude then applies each change to the .tex by hand. With
--accept, the live file is copied over the baseline afterwards so the next sync starts here.
"""
import difflib, json, shutil, sys


def fields(d):
    out = {}
    for k in ("title", "authors", "affiliations", "impact"):
        if k in d:
            out[k] = (k.capitalize(), d[k])
    for s in d.get("synopsis", []):
        out["synopsis." + s["id"]] = ("Synopsis · " + s.get("label", "").rstrip(":"), s["text"])
    for b in d.get("body", []):
        if b.get("label"):
            out["label." + b["id"]] = (b["section"] + " · heading", b["label"])
        out["body." + b["id"]] = (b["section"] + (" · " + b["label"].rstrip(".") if b.get("label") else ""), b["text"])
    for i, c in enumerate(d.get("figures", []), 1):
        out["figures." + c["id"]] = ("Figure %d caption" % i, c["text"])
    for i, r in enumerate(d.get("references", []), 1):
        out["references." + r["id"]] = ("Reference %d" % i, r["text"])
    return out


def word_diff(a, b):
    A, B = a.split(), b.split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, A, B).get_opcodes():
        if op == "equal":
            seg = A[i1:i2]
            out.append(" ".join(seg) if len(seg) <= 8 else " ".join(seg[:4]) + " … " + " ".join(seg[-4:]))
        else:
            if i2 > i1:
                out.append("[-" + " ".join(A[i1:i2]) + "-]")
            if j2 > j1:
                out.append("{+" + " ".join(B[j1:j2]) + "+}")
    return " ".join(out)


def main():
    a = sys.argv[1:]
    if len(a) < 2:
        sys.exit(__doc__)
    base, live = (json.load(open(p, encoding="utf-8")) for p in a[:2])
    fb, fl = fields(base), fields(live)
    seen = {(e.get("at"), e.get("by")) for e in base.get("history", [])}
    new_hist = [e for e in live.get("history", []) if (e.get("at"), e.get("by")) not in seen]
    by_key = {}
    for e in new_hist:
        for c in e.get("changes", []):
            by_key.setdefault(c["key"], []).append("%s by %s" % (e.get("at", "?"), e.get("by", "?")))

    changed = [k for k in fl if k in fb and fl[k][1] != fb[k][1]]
    added = [k for k in fl if k not in fb]
    removed = [k for k in fb if k not in fl]
    print("%d changed field(s), %d new history entr%s, %d distinct editor id(s)" % (
        len(changed), len(new_hist), "y" if len(new_hist) == 1 else "ies", len({e.get("by") for e in new_hist})))
    for k in changed:
        print("\n== %s  [%s]" % (fl[k][0], k))
        print("   edits: " + ("; ".join(by_key.get(k, [])) or "none recorded"))
        print("   OLD: " + fb[k][1])
        print("   NEW: " + fl[k][1])
        print("   DIFF: " + word_diff(fb[k][1], fl[k][1]))
    for k in added:
        print("\n++ new field %s: %s" % (k, fl[k][1]))
    for k in removed:
        print("\n-- field removed %s" % k)
    if "--accept" in a:
        shutil.copyfile(a[1], a[0])
        print("\nbaseline updated:", a[0])


if __name__ == "__main__":
    main()
