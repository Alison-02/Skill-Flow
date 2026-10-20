# The generated skill

**Generate SKILL.md** writes a normal skill folder, `out/fluxo-<name>/`, inside the data folder:

```text
out/fluxo-relatorio-mensal-exemplo/
├── SKILL.md                       the orchestrator Claude follows
└── registro-da-execucao.md        optional template for the run record
```

Copy the folder to wherever Claude loads skills (for example `~/.claude/skills/`) and ask Claude to run it. Complete generated files, produced from the bundled examples, are in [`example-output/`](example-output): [`relatorio-mensal`](example-output/relatorio-mensal/SKILL.md) and [`consultas-a-bancos`](example-output/consultas-a-bancos/SKILL.md).

> The text is in Brazilian Portuguese because that is the language the editor currently generates. The structure below is what matters.

## Anatomy

### 1. Front matter

```yaml
---
name: fluxo-relatorio-mensal-exemplo
description: Usar ao produzir o relatório mensal de métricas de um projeto, da coleta dos dados à conferência final.
---
```

The `description` comes from the flow's *"When to use this flow"* field. It is what lets Claude decide to use the skill, so write it like any skill description.

### 2. How to execute

A fixed block of rules that turn the list of steps into a procedure. In short: run the steps **in order, one at a time**; use **only the source named in each step** (and for a section, read only that section, not the whole file); check each step's **proof of completion** before moving on; on a missing source or something that does not match, **stop and ask**; follow **only the branch whose condition is true** and say which one and why; respect **database rules** (read-only means read-only, never handle secrets); and write each branch decision into the run record.

### 3. Inputs

If the flow has parameters, a section says which values to **ask for before step 1**, which are required, and which are derived (computed from others, not asked). With *Generate with values…*, it instead lists the values already filled in.

```markdown
## Entradas (obtenha ANTES da etapa 1)
- `{projeto}` — Projeto (obrigatório) — código do projeto
- `{periodo}` — Período (MM/AAAA) (obrigatório)
```

### 4. Flow map

A [Mermaid](https://mermaid.js.org/) diagram of the whole flow (diamonds for decisions, hexagons for checks, dashed lines for doubt and loop returns), drawn by GitHub and most Markdown viewers. It is only for orientation; the numbered steps are the source of truth. You can turn it off in the flow's settings.

### 5. Run record

When the option is on, the skill tells Claude to keep a record of the run and to **resume from it** in another conversation: copy the template, mark each step *done (with proof)*, *blocked (reason)* or *skipped*, log every branch decision with its evidence, and never redo a step that already has proof.

### 6. The steps

Each step is a numbered section. What it contains depends on the node:

```markdown
## Etapa 3 — Trecho de skill: Fluxo do mês (relatorio-mensal-de-metricas)
- NÃO carregue a skill `relatorio-mensal-de-metricas` inteira. Leia apenas a seção «Fluxo do mês» do arquivo
  `{SKILLS}/relatorio-mensal-de-metricas/SKILL.md` (linhas ≈ 19–24; se não bater, localize pelo título).
- Aplique só o que essa seção diz; se ela remeter a outra referência, abra apenas a remissão.
- Nesta etapa: Seguir a ordem padrão do mês
- Recebe de: etapa 2
- Depois: vá para a etapa 4.
```

- **Source lines** (*load this skill*, *read only this section*, *use this tool*, *query this database*) and your **instruction**.
- **Receives from**: the previous step(s), which is also how rejoining branches are recognized.
- **Next**: the next step, or the labeled branches and the doubt exit for a decision:

  ```markdown
  - Depois (siga o ramo cuja condição for verdadeira):
    - sim, há divergência → etapa 7
    - não → etapa 9
    - nenhuma condição acima é verdadeira com certeza, ou há dúvida → PARE: relate as leituras possíveis, …
  ```
- **Proof of completion**, from the node. When a step reads a section of a skill that ends with its own *"Prova de que terminou"* section, the run record's *expected proof* points to it.
- **Loops** say what to repeat, the safety limit, where the body starts, where it returns and what comes after.
- **Database queries** carry access, filters, expectation, suggested SQL and the `{names}` to store ([details](database-queries.md)).
- A step for a *doubt exit* ("report what was found and ask the user") can be created with one click in the inspector, so a decision never dead-ends.

Paths under your skills folder are written as `{SKILLS}/…`, and the folder itself is declared once in the rules at the top. Only paths under the first skills folder found become `{SKILLS}`; paths to `CLAUDE.md` files and to other folders stay absolute and must be adjusted by hand when you move the skill to another machine.

## Tips

- **Write the flow's description** like a skill description: a trigger sentence, not a title.
- Give every *Condition* a *how to decide* line ("where to look") and a label for every branch; the checks will remind you.
- Put real evidence in **proofs of completion** ("3 rows read", "file saved"): Claude records what it obtained against what was expected.
- Prefer **sections** over whole skills. The point of the flow is that Claude reads only what the step needs.
- Regenerate after editing the source skills: the editor tells you when a section a flow depends on changed.
