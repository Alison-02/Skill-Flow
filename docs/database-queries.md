# Database queries

A **Database query** node (*Consulta ao banco*) tells Claude to fetch one specific piece of information from a database in the middle of a flow, and to keep the result as `{names}` that later steps can use.

**Skill Flow never connects to a database.** You *describe* the database; the generated skill tells Claude how to reach it (through the way you declared) and what to ask for. Credentials are never stored. See [Secrets](#secrets).

A ready-made example flow is at `/?demo=consultas` (start the server with `--data examples/data`), and its generated output is in [example-output/consultas-a-bancos](example-output/consultas-a-bancos/SKILL.md).

## 1. Declare your databases

Open **Databases…** in the left panel. For each database set:

| Field | Meaning |
|---|---|
| **Name** | Shown in the editor and quoted in the generated skill. |
| **Type** | PostgreSQL, MySQL / MariaDB, SQL Server, SQLite, spreadsheet, JSON file, API / HTTP or other. The type decides how the suggested query is written. |
| **How Claude accesses it** | See the table below. |
| **Read-only** | On by default. The generated text then says *do not write, alter or delete anything in this database*. |
| **ID at the provider and schema** | Optional, for PostgreSQL, MySQL and SQL Server. The text tells Claude to use that ID to pick the database at the provider, and qualifies tables with the schema when it is not `public`. |
| **Tables and columns** | One column per line, `name — description`. They feed the pickers in the query node and the checks. |
| **Note** | Free text for Claude. |

| Access method | Use it when | What you fill in |
|---|---|---|
| **MCP connector** (local or cloud) | A database or SaaS tool is exposed to Claude as an MCP tool. | The tool name (when you start the editor with `/skill-flow`, the list suggests the MCP tools Claude has) and optional fixed arguments. |
| **Command line** (local) | A local CLI can read the data (`sqlite3`, `psql`…). | The read command. |
| **Read the file** (local) | A spreadsheet, CSV or JSON file. | The path (and the sheet). |
| **HTTP API** (cloud) | A REST endpoint. | The base URL and the **name** of an environment variable that holds the key (for example `MY_API_KEY`), never the key itself. |
| **Ask the user** | The data lives somewhere Claude cannot reach. | Nothing; the step asks the user for the values. |

The declarations live in `config.json` (`databases`). Nothing else is needed for local or cloud: the *how* is just text for Claude.

## 2. Add the node

Drag **Database query** from the *Logic* group (or click *Consultar* + the table name (*Query* `<table>`) under a database in the left panel). In the inspector:

- **Database** and **Table**.
- **Fields to fetch → store as {name}**: click a column to add it, then give the `{name}` it is stored under. For a list, the fields are the item's columns.
- **Filter** (all conditions must hold): column, operator (`=`, `≠`, `>`, `<`, `≥`, `≤`, *contains*, *is empty*) and a value, which can be a `{parameter}` or an earlier `{name}`.
- **What to expect**:
  - **exactly 1 record**: zero or two-or-more is treated as "not found";
  - **the first of an order**: pick the column and ascending or descending; empty values in that column are ignored;
  - **a list**: give the list a `{name}`; it can feed a *for each* loop, and each item's fields are available as `{names}` inside the loop.
- A **doubt exit** (*If nothing is found, more than one comes back, or the access fails…*) to send the flow to a step of your choice. Without one, the generated text says to **stop and ask the user and never invent values**.

The **How it appears in SKILL.md** box shows the exact text Claude will receive.

## 3. What the generated step says

```markdown
## Etapa 2 — Consulta ao banco: Buscar as métricas do mês
- Consulta ao banco «Métricas do produto (exemplo)» (SQLite (arquivo local)).
- Como acessar: no terminal, `sqlite3 -readonly metricas.db`. Use só comandos de leitura. …
- SOMENTE LEITURA: não grave, não altere e não apague nada neste banco.
- O que buscar: tabela `metricas_mensais`; campos `usuarios_ativos`, `receita`.
- Filtro: `projeto` = `{projeto}` E `periodo` = `{periodo}`.
- Esperado: exatamente 1 registro (se vierem 2 ou mais, é "mais de um").
- Consulta sugerida (…): `SELECT usuarios_ativos, receita FROM metricas_mensais WHERE projeto = '{projeto}' AND periodo = '{periodo}' LIMIT 2;`
- Guarde o resultado: `usuarios_ativos` → {usuarios}; `receita` → {receita}. …
- Se não encontrar, vier mais de um ou der erro de acesso: vá para a etapa 11.
```

The text names the access method, repeats the read-only rule, says what to fetch and with which filter, what to expect, a suggested query (for SQL engines), where to store each value and where to go if it fails.

### How the suggested SQL is written

- **Row limits.** *One record* asks for 2 rows (so "more than one" is detectable); *first* asks for 1; a *list* asks for **200** (`TOP 200` on SQL Server) and tells Claude to stop and ask if exactly 200 come back, since there may be more.
- **Quoting.** Identifiers are quoted per engine (double quotes, backticks for MySQL and SQLite, brackets for SQL Server) only when needed: reserved words, capitals, spaces or special characters in a name (a name with a dot, like `a.b`, is read as `schema.table`).
- **Literals** are always quoted, with single quotes doubled (MySQL also doubles backslashes), so a code like `0042` is never turned into the number `42`. In `>`, `<`, `≥`, `≤` comparisons, a numeric value is written as a number (`1.000,50` becomes `1000.50`).
- **Contains** becomes `LIKE` (`ILIKE` on PostgreSQL) with `%` and `_` escaped. **Is empty** matches both `NULL` and `''`.
- **Not SQL?** Spreadsheets, JSON files and APIs are described in words, with no SQL. For HTTP, the text asks for filters as request parameters (URL-encoded) and for **at most 200** records on lists.

## 4. Using the values

`{names}` filled by a query can be used in any later step's instruction, in a filter value, in a loop's list, and in titles. The editor checks, and shows on the node:

- a `{name}` used on a path that can skip the query that fills it (loops that always run once and branches that rejoin are understood);
- two queries filling the same `{name}` on the same path, a name that collides with a parameter, or an invalid name;
- a query with no database, table, columns or filter value, a list with no filter (up to 200 records), a table or column the database does not declare, and a database that no longer exists.

Renaming a stored `{name}` in the query renames it in the instructions too, unless another query also fills it.

## Secrets

- **Never type a password or API key in a field.** For HTTP access, write only the **name** of an environment variable. The generated text tells Claude to use it by reference (`$MY_API_KEY`) and never to print, write or log its value.
- When you save the **Databases…** window, the server checks every field:
  - **Unmistakable credentials** (JWTs, `sk-…`, `ghp_…`, `sbp_…`, cloud access keys, `user:password@` in a connection string…) are **rejected** (HTTP 400).
  - Text that **looks like** a secret (`password=…`, `senha: …`, a JSON `"password"`, `mysql -p…`, `sqlcmd -P …`, `curl -u user:pass`, a long random token…) makes the window **ask**, showing the database, the field and a masked excerpt. If you confirm, only *that exact text* is accepted, and the decision is remembered so you are not asked again for the same text.
- This is a safety net with known limits (a loose sentence like "user leitor, senha Abc123" slips through). Treat it as a seatbelt, not a vault: keep secrets in environment variables or in your connector's own configuration.

## What it does not do

It does not run the query, test the connection, validate that columns exist in the real database, or know your data. The checks compare the node with what you declared. Claude does the querying, through the access you described, and stops and asks when something is off.
