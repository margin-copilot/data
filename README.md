# Margin Copilot: data

Margin Copilot data: synthetic dataset generator, RLS scripts, policy documents, indexer.

Part of **Margin Copilot**, a secure multi-agent pricing assistant on Azure, built as a personal learning project.

**Start here:** [margin-copilot/docs](https://github.com/margin-copilot/docs) explains how the whole system works and how the repos fit together.

## What's in it

- `riad_data.generate`: one year of sales for 9 stores and 30 products (98,460 rows), deterministic with seed 42. Dairy margins hit the monthly targets, and the six planted stories are built in: the North dairy drop, Ramadan demand, the South water price match, the Center tomato spike, the Center olive oil increase and the Guelmim closure.
- `riad_data.checks`: a story check for every planted fact the eval cases rely on.
- `riad_data.tables`: Delta tables (written by delta-rs, no Spark) under `Tables/dbo/` and `Tables/rls/`.
- `riad_data.rls`: the T-SQL security policy. Every table with `region_id` is filtered by the caller's UPN through `rls.user_region`, which test users can't read.
- `riad-fabric`: sets up the Fabric workspace and lakehouse, loads the tables and applies the policy, after one browser sign-in as the Fabric admin.

## Run and test

```bash
uv sync
uv run pytest -q                      # generator, story checks, tables, SQL, Fabric client
cp .env.example .env                  # fill in; see the comments
uv run riad-fabric all                # setup + load + rls (browser sign-in as the Fabric admin)
uv run riad-fabric verify
```

How region security fits the whole system: [security model](https://github.com/margin-copilot/docs/blob/main/security-model.md).

## License

MIT. See [LICENSE](LICENSE).
