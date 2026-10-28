# ISMRM2027-abstract-skill

A [Claude Code](https://claude.com/claude-code) skill (`/shared-abstract`) for co-editing a LaTeX conference abstract with your co-authors.

It turns a `.tex` abstract (ISMRM-style or similar) into a private web page on claude.ai. Co-authors click any text to edit it and press **Save**. The page shows live word/character-limit counters and a change history of who changed what. Claude then pulls the saved edits back into your `.tex` and rebuilds the PDF.

```
 abstract.tex ──tex2json.py──▶ data/abstract.json ──publish──▶ claude.ai page ◀── co-authors edit + Save
      ▲                                                               │
      └──── Claude applies edits, rebuilds PDF ◀── sync_edits.py ◀────┘ (read)
```

## Requirements

- **Claude Code**, logged in with your claude.ai account. The page is published to that account.
- **Python 3**. The scripts use only the standard library. Pillow is optional; on macOS, `sips` is used without it.
- Your usual LaTeX toolchain (`xelatex` / `pdflatex`) to rebuild the PDF.
- `pdftoppm` (poppler) or macOS `sips` if any figures are PDF/EPS.
- Co-authors only need a claude.ai account in the same organization (or an invite). They don't need Claude Code.

## Install

```bash
git clone https://github.com/QiangLiu0310/ISMRM2027-abstract-skill.git
cp -r ISMRM2027-abstract-skill/shared-abstract ~/.claude/skills/
```

Restart Claude Code or start a new session. `/shared-abstract` should then appear in the skill list.

## Use

Run these from the folder that holds your abstract:

| You say | What happens |
|---|---|
| `/shared-abstract publish latex/abstract.tex` | Converts the `.tex` to page data and makes web copies of the figures. Claude checks the conversion, then publishes a private page and gives you the link. |
| `/shared-abstract sync` | Pulls the saved edits from the page, shows what changed and who changed it, applies the changes to the `.tex` (after a backup), rebuilds the PDF and re-checks the limits. |
| `/shared-abstract push` | Syncs first, then sends your own `.tex` edits up to the page. |

The default ISMRM limits are body 750 words, synopsis 100 words, impact 40 words and captions 500 characters. For other conferences Claude asks for the limits.

The skill expects the usual abstract layout: a title, authors and affiliations, `\section*{…}` headings, figures with `\caption{}`, and a numbered reference list. "Impact" and "Synopsis" sections are optional. Claude reviews the converted text before publishing, so unusual macros and equations get fixed by hand.

## Sharing with co-authors

1. Open the page link and use **Share**. Give each co-author **edit** access. Anyone with view-only access sees a read-only page.
2. Co-authors click any text to edit it, then press **Save changes** (or ⌘/Ctrl-S). If two people save at once, the second person's unsaved edits are kept and reapplied on top of the newer version.
3. **History** shows every saved change as a word-level diff, with the editor's name.

## Repository layout

```
shared-abstract/
  SKILL.md                 instructions Claude follows (publish / sync / push)
  template/abstract.html   the editable page; reads data/abstract.json
  scripts/tex2json.py      .tex  -> data/abstract.json
  scripts/make_figs.py     figures -> fig/figN.jpg (white background, ≤2000 px)
  scripts/sync_edits.py    what changed on the page since the last sync
```

## Page data model (`data/abstract.json`)

| Field | Type | Notes |
|---|---|---|
| `title`, `authors`, `affiliations` | string | |
| `impact` | string | optional |
| `synopsis` | `[{id, label, text}]` | optional |
| `body` | `[{id, section, label, text}]` | one block per paragraph |
| `figures` | `[{id, file, text}]` | `text` is the caption |
| `references` | `[{id, text}]` | |
| `limits` | `{body, synopsis, impact, caption}` | words, except `caption` in characters (counted with the "Figure N. " prefix) |
| `header` | string | top-bar text |
| `history` | `[{at, by, changes:[{key, name, before, after}]}]` | written by the page; last 300 saves kept |

Text is plain Unicode except math: `$…$` (inline) and `$$…$$` (display) hold LaTeX rendered with MathJax, and `\$` is a literal dollar sign. Sync matches fields by `id`, so ids must never be regenerated after the page is shared.

## Functions

### `scripts/tex2json.py`

```
python3 tex2json.py abstract.tex out_dir [--limits body=750,synopsis=100,impact=40,caption=500] [--header "ISMRM 2027 · My Abstract"]
```

Writes `out_dir/data/abstract.json`, prints the figure sources in order, and prints a `WARNING` for every piece of LaTeX it couldn't convert.

| Function | What it does |
|---|---|
| `group(s, i)` | With `s[i] == '{'`, returns the brace-balanced content and the index after the matching `}`. Skips escaped characters. |
| `arg(s, i)` | Reads one macro argument at `s[i]`: skips spaces and a `[optional]` argument, then returns a `{group}`, a single macro or a single character. |
| `script(text, table, mark)` | Maps `^{…}`/`_{…}` to Unicode super/subscripts when every character has one, otherwise keeps `^`/`_` notation. |
| `conv(s, math=False)` | The core LaTeX → Unicode converter: Greek letters, symbols, accents, `\textsuperscript`/`\textsubscript`, `--`/`---`, `~`, formatting macros (dropped), and inline/display math (kept as `$…$` / `$$…$$`). Unknown macros are recorded as warnings. |
| `slug(s, used)` | Makes a short, unique, URL-safe id (≤24 chars) for a block. |
| `lead_label(p)` | Splits a leading `\para{…}`, `\textbf{…}` or `\paragraph{…}` off a paragraph and returns it as the block label. |
| `main()` | Strips comments; reads title/authors/affiliations (from `\title`/`\author` or a `center` block); collects figure environments; splits the rest by `\section` into impact, synopsis, references and body blocks; writes the JSON. |

### `scripts/make_figs.py`

```
python3 make_figs.py out_dir src1.png src2.pdf ...     # sources in figure order
```

| Function | What it does |
|---|---|
| `rasterize(src, tmp)` | Renders the first page of a PDF/EPS to PNG at 300 dpi (`pdftoppm`, falling back to `sips`). Other formats pass through. |
| `convert(src, dst)` | Flattens transparency onto white, downsizes to ≤2000 px wide and saves JPEG at quality 88 (Pillow, or `sips` without it). |
| `main()` | Writes `out_dir/fig/fig1.jpg`, `fig2.jpg`, … and prints each output size. |

### `scripts/sync_edits.py`

```
python3 sync_edits.py baseline.json live.json [--accept]
```

`baseline.json` is the local `shared_page/data/abstract.json` (the last synced state); `live.json` is the copy just pulled from the page.

| Function | What it does |
|---|---|
| `fields(d)` | Flattens the JSON into `{key: (readable name, text)}`, e.g. `body.<id>`, `label.<id>`, `figures.<id>`, `references.<id>`. Keys match the ones the page writes into `history`. |
| `word_diff(a, b)` | Word-level diff as `[-removed-] {+added+}`, eliding long unchanged runs. |
| `main()` | Reports changed, added and removed fields with old/new text, the diff and the history entries (time, editor id) behind each one. `--accept` then copies the live file over the baseline. |

### `template/abstract.html` (page JavaScript)

The page uses the claude.ai artifact runtime: the `artifact` capability to save (republish `data/abstract.json`) and the `user` capability to identify the editor and check edit access.

| Function | What it does |
|---|---|
| `boot()` | Loads `data/abstract.json`, renders it, loads MathJax, checks edit access and switches to read-only if saving isn't possible, then restores any unsaved draft. |
| `render()` | Builds the page (title block, synopsis, body, figures, references) with every text field editable. |
| `fields(d)` | Lists every editable field with a key, display name and getter/setter, mirroring `fields()` in `sync_edits.py`. |
| `ed(key, text, tag)` | Creates one editable element for a field. |
| `splitMath(s)` / `renderMath(s)` / `stripMath(s)` | Split text into prose and `$…$` math; render math as SVG; replace math with a placeholder for word counting. |
| `loadMath()` | Loads MathJax on demand. Fields with math show rendered output and switch to source while being edited. |
| `caretEnd(el)` | Moves the caret to the end of a field when it switches to source view. |
| `current()` / `dirtyKeys()` | The current text of every field, and which fields differ from the saved version. |
| `onInput(e)` | Tracks edits, keeps a draft in `sessionStorage`, enables Save and refreshes the counters. |
| `chip(...)` / `updateCounts()` | Live word/character counters, highlighted when a section is over its limit. |
| `save()` | Appends a history entry (`at`, `by`, per-field `before`/`after`) and republishes the JSON. Handles save conflicts (keeps and reapplies your draft) and missing edit access. |
| `diff(a, b)` / `renderHistory()` | Word-level diff and the History panel, newest first, with editor names. |
| `savedStatus()` | "Last saved …" status text. |
| `showReadOnly()` | Hides Save and shows the read-only notice. |
| `restoreDraft()` | Reapplies unsaved edits from `sessionStorage` on top of the latest saved version (e.g. after a conflict reload). |

## Good to know

- Edits live on the page until you run **sync**. Nothing changes your `.tex` automatically.
- Sync only updates the `.tex`. If you also keep a Word copy, ask Claude to update it separately.
- Don't regenerate the page from the `.tex` after you've shared it. That resets the history and breaks sync. Use **push** instead.
- The page and its figures are visible to anyone you share it with. Don't put unpublished data on it that some co-authors shouldn't see.
