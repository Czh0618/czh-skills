---
name: mysql-cli
description: Safe MySQL exploration and querying for agents. Use when Codex or Claude Code needs to inspect MySQL databases, list schemas or tables, describe table columns and indexes, sample rows, run read-only SQL, diagnose SQL errors, or manage local MySQL connection profiles through the bundled `mydb` CLI.
---

# MySQL CLI

Use the bundled `mydb` CLI as the database access boundary. Run commands from
the directory containing this `SKILL.md` with `uv run mydb ...`.

## Agent Rules

- Prefer `--json` for every command so stdout is a pure `{ok, schema_version, data|error}` envelope.
- Treat read-only as the default. Do not run `mydb exec --allow-write` unless the user explicitly asked for a write/DDL operation.
- Prefer profiles created with `--readonly-locked` for exploration.
- `--profile` works either before the subcommand or on supported subcommands; examples use the subcommand form.
- Do not echo passwords in commands or write secrets to project files. Use the configured password environment variable or `~/.mydb-cli/.env`.
- If an error envelope is returned, branch on `error.code` instead of string matching the message.

## Setup

Create a profile:

```bash
uv run mydb conn add prod --host HOST --user USER --db DB --readonly-locked --json
```

Set the password outside the project workspace:

```bash
export MYDB_PWD_PROD=...
```

Or place it in `~/.mydb-cli/.env`:

```bash
MYDB_PWD_PROD=...
```

Test connectivity:

```bash
uv run mydb conn test --profile prod --json
```

## Safe Exploration

```bash
uv run mydb databases --profile prod --json
uv run mydb tables --profile prod --db shop --json
uv run mydb describe users --profile prod --json
uv run mydb indexes users --profile prod --json
uv run mydb sample users --profile prod --limit 10 --json
uv run mydb query "SELECT id, email FROM users WHERE id = 1" --profile prod --limit 20 --json
```

`query` automatically appends `LIMIT n` to bare `SELECT` and `WITH` statements
that do not already include a limit. Schema commands and samples are read-only.

## Error Codes

- `not_connected`: no current profile; pass `--profile` or run `conn use`.
- `profile_not_found`: the requested profile does not exist.
- `password_not_set`: set the password environment variable shown in the error.
- `write_not_allowed`: the SQL was classified as write/DDL and was blocked.
- `confirmation_required`: dangerous SQL needs `-y`, and only after explicit user approval.
- `connection_error`: network, authentication, or connection setup failed.
- `query_error`: MySQL rejected the statement.

## Writes

Only use writes after explicit user instruction:

```bash
uv run mydb exec "UPDATE users SET status = 'disabled' WHERE id = 1" --profile prod --allow-write --json
```

For `DROP`, `TRUNCATE`, `ALTER`, or `UPDATE`/`DELETE` without `WHERE`, require
separate confirmation and add `-y`.
