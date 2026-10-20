# Concepts

> The interface and the generated text are in Brazilian Portuguese. Portuguese UI labels appear in *italics* next to the English names used here.

## Flow

A **flow** is a graph of nodes saved as JSON in the data folder (`flows/<name>.json`). It has a name, a *description* (which becomes the `description` of the generated skill, so write it as "use this when…"), optional **parameters**, optional **groups** (visual phases) and a run-record option.

## Nodes

Every node has a **title**, an **instruction** (what to do in this step, which may use `{parameters}`), an optional **proof of completion** and can be switched off (key <kbd>D</kbd>): it then disappears from the generated text and its connections pass straight through (a switched-off step that has branches stays, and the logic check says so).

| Node (*UI label*) | Source | What it generates |
|---|---|---|
| Start (*Início*) | none | The entry: what the user must provide to begin. |
| Skill (*Skill inteira*) | a skill | "Load skill `x` with the `Skill` tool and follow it." |
| Skill section (*Trecho de skill*) | one heading of a `SKILL.md` | "Do **not** load the skill; read only section «H» of this file." Line numbers are hints; Claude finds the section by its title. |
| Skill reference (*Referência da skill*) | a file under `references/`, whole or one heading | "Read only section «H» of the reference file." |
| CLAUDE.md section (*Trecho do CLAUDE.md*) | one heading of a `CLAUDE.md` | "Read only section «H» and apply it as a rule." |
| Tool (*Ferramenta*) | a Claude tool | "Use the tool `x`." |
| Database (*Banco de dados*) | a declared database | How to reach it, whether it is read-only, and what to look for. |
| Database query (*Consulta ao banco*) | a declared database and table | The columns, filter, expectation and the `{names}` that store the results. See [database-queries.md](database-queries.md). |
| Step (*Etapa*) | none | "Do: …" followed by your instruction. |
| Condition (*Condição*) | none | A decision; the branch is chosen by the **label on each outgoing connection**. |
| Check (*Conferência*) | none | A criterion that must hold before moving on. |
| Loop (*Laço*) | none | `For each` item of a list, or `repeat until` a condition, with a turn limit. |
| Sub-flow (*Subfluxo*) | another saved flow | The other flow's steps, expanded in place; its parameters become yours. |
| Note (*Nota*) | none | Nothing: notes never reach the generated text. |
| End (*Fim*) | none | What must be delivered. |

## Connections

- A connection from A to B means "after A, go to B". A node with a single outgoing connection just continues.
- A **Condition** (or a **Check** with several exits) needs a **written label on each branch**. Claude follows only the branch whose label is true, with the evidence in view, and writes the choice in the run record's *path taken*.
- The **doubt exit** (*Se houver dúvida…*, chosen in the inspector) is the step to go to when no branch is clearly true or two seem to be. Without one, the generated text says: stop, report the possible readings with evidence, and ask the user.
- **Loops** have two outputs: *body* (what repeats) and *done* (what comes after). The last step of the body connects back to the loop node, drawn as a dashed return. A loop is either **for each** (over a list you name, usually a `{list}` filled by a query) or **until** a condition, checked before or after each turn, and always has a **maximum number of turns**; reaching it stops and asks.
- Branches that rejoin are recognized: the step they rejoin at lists several origins in its *Receives from* line.

## Parameters

Write `{name}` (lowercase letters, digits and `_`) in any instruction, title, label or source text. The generated skill then starts with an **Inputs** section that tells Claude to ask for the required values first.

- **+ Project and period** adds a ready-made set (the names are in Portuguese): `projeto`, `periodo` (`MM/AAAA`), and values *derived* from the period: `mes`, `ano`, `data_ini` and `data_fim_mes` (`YYYY-MM-DD`), plus `pasta_saida`, an output folder. Parameter names are free: lowercase letters, digits and `_`, starting with a letter.
- **Generate with values…** fills the parameters in the text and the run-record path, for a ready-to-run, single-use skill.
- A `{name}` that appears in your sources but has no parameter is listed so you can declare it with one click. Values filled by a *Database query* count as declared.

## Logic checks

The inspector's **Logic check** panel and the mark on each node report, among other things:

- a branch with no condition, or two branches with the same condition, or a decision with fewer than two branches;
- a decision or check that does not say *how to decide* (where to look);
- steps that cannot be reached from the start, or that lead nowhere without being an *End*;
- loops with no body, no return connection or no stop condition;
- a disabled step that still has branches;
- a *Database query* with no database, table, columns or filter value, a duplicated `{name}`, a name that collides with a parameter, or a step that uses a value on a path that may skip the query that fills it.

Errors block nothing, but **Generate** includes them in its warnings.

## Change detection

When you add a skill section or reference to a flow, the editor stores a **fingerprint** (ignoring line endings and trailing spaces) and a copy of the text you reviewed. Each time the flow opens, the editor compares:

- **changed** (*mudou*): the section's text is different; the node gets an amber border and a banner at the top, you can see a **diff**, and you can **accept** the change (*Aceitar a mudança*) to make the new text the reference;
- **missing** (*sumiu*): the heading or file no longer exists; use **Swap the source** (*Trocar a fonte*) to point the node at another section **without losing its connections, title, instruction or proof**, or **Repair sources** in the command bar to reconnect the ones that have an obvious replacement.

## Run record

Optionally, **Generate** writes `registro-da-execucao.md` next to the `SKILL.md`: a template with the **state of each step** (not started / in progress / done with proof / blocked / skipped), the **proof expected and obtained**, the **path taken** (each decision and why), express approvals, writes performed, decisions, pending items and lessons learned. The generated skill tells Claude to copy it, fill the copy, and to **resume from the path taken** if a record already exists.

## Measure

**Measure** (*Medir*) keeps a small log of real runs done *with* and *without* the flow (project, period, time, rework, findings by severity and the step each finding belongs to) and compares them. It only knows what you register. For a fair comparison, redo a run you already verified, with and without the flow.

## Groups, notes and layout

Select nodes and press <kbd>Ctrl</kbd>+<kbd>G</kbd> to group them into a named phase (shown as a heading in the generated text). **Organize** lays the flow out automatically: *Horizontal* (left to right, parallel branches side by side, wrapping only if too wide), single-line horizontal, or *bands* of N columns. Everything is undoable.

## Keyboard shortcuts

| Action | Keys |
|---|---|
| Command bar | <kbd>Ctrl</kbd>+<kbd>K</kbd> |
| Help | <kbd>?</kbd> |
| Pan | scroll · <kbd>Shift</kbd>+scroll sideways · <kbd>Space</kbd>+drag · middle button+drag |
| Zoom | <kbd>Ctrl</kbd>+scroll, <kbd>+</kbd> / <kbd>-</kbd>, <kbd>0</kbd> for 100%, <kbd>1</kbd> to fit |
| Select | drag on the background, <kbd>Shift</kbd>+click, <kbd>Ctrl</kbd>+<kbd>A</kbd>, <kbd>Esc</kbd> |
| Copy / cut / paste / duplicate | <kbd>Ctrl</kbd>+<kbd>C</kbd> / <kbd>X</kbd> / <kbd>V</kbd> / <kbd>D</kbd> |
| Delete · disable | <kbd>Delete</kbd> · <kbd>D</kbd> |
| Rename · edit instruction | <kbd>F2</kbd> · <kbd>Enter</kbd> |
| Move between nodes | arrow keys; <kbd>Shift</kbd>+<kbd>←</kbd>/<kbd>→</kbd> selects everything on that side |
| Add a note | <kbd>Shift</kbd>+<kbd>S</kbd> |
| Search the left panel | <kbd>N</kbd> |
| Undo / redo | <kbd>Ctrl</kbd>+<kbd>Z</kbd> / <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Z</kbd> |
| Save · new flow | <kbd>Ctrl</kbd>+<kbd>S</kbd> · <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>N</kbd> |
| Group · ungroup | <kbd>Ctrl</kbd>+<kbd>G</kbd> · <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>G</kbd> |
| Expand · collapse all groups | <kbd>Alt</kbd>+<kbd>G</kbd> · <kbd>Shift</kbd>+<kbd>Alt</kbd>+<kbd>G</kbd> |
| Organize | <kbd>Shift</kbd>+<kbd>Alt</kbd>+<kbd>T</kbd> |
| Generate SKILL.md | <kbd>Ctrl</kbd>+<kbd>Enter</kbd> |

On touch screens, drag the background to pan, pinch with two fingers to zoom and tap to select; use the **+** button in the left panel instead of dragging items onto the canvas.
