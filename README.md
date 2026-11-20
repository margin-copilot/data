# Margin Copilot: data

Margin Copilot data: synthetic dataset generator, RLS scripts, policy documents, indexer.

Part of **Margin Copilot**, a secure multi-agent pricing assistant on Azure, built as a personal learning project.

**Start here:** [margin-copilot/docs](https://github.com/margin-copilot/docs) explains how the whole system works and how the repos fit together.

## What's in it

- `riad_data.generate`: one year of sales for 9 stores and 30 products (98,460 rows), deterministic with seed 42. Dairy margins hit the monthly targets, and the six planted stories are built in: the North dairy drop, Ramadan demand, the South water price match, the Center tomato spike, the Center olive oil increase and the Guelmim closure.
- `riad_data.checks`: a story check for every planted fact the eval cases rely on.
- `riad_data.tables` and `riad_data.load`: the T-SQL tables and the loader. It creates users and the reader role first, then loads tables, rows and the security policy in one transaction, so a reload never shows unfiltered rows.
- `riad_data.rls`: the security policy. Every table with `region_id` is filtered by the caller's sign-in name (`ORIGINAL_LOGIN()`) through `rls.user_region`, which test users can't read.
- `riad-data`: loads and verifies the database after one browser sign-in as the database admin.

## Run and test

```bash
uv sync
uv run pytest -q                      # generator, story checks, tables, loader, SQL helpers
cp .env.example .env                  # fill in; see the comments
uv run riad-data load                 # browser sign-in as the database admin
uv run riad-data verify
```

The database's firewall admits one public IP. If yours changes (error 40615), re-run the deploy in the infra repo. A paused free database takes up to a minute to wake; `riad-data` retries.

How region security fits the whole system: [security model](https://github.com/margin-copilot/docs/blob/main/security-model.md).

## Policies

`policies/*.md` holds Riad Market's seven pricing policies (46 clauses), transcribed from the [policy corpus](https://github.com/margin-copilot/docs). Each file has front matter (`id`, `title`, `audience`) and clauses as `## §N Title`, or `### N.M` sub-clauses under it. Audiences are `all`, `north`, `center`, `south` and `directors`; `POLICY_GROUPS` maps them to Entra group IDs.

```bash
uv run riad-data policies    # browser sign-in as the admin; pushes one AI Search document per clause
```

It creates or updates the `policies` index, uploads every clause with the group IDs allowed to read it, and removes clauses no longer in the corpus. The policy agent filters on the caller's groups (D-009, D-036 in the docs repo).

## License

MIT. See [LICENSE](LICENSE).
