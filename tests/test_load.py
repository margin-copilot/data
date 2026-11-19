from riad_data.generate import generate
from riad_data.load import CHUNK, load
from riad_data.tables import user_region_rows


class Recorder:
    def __init__(self):
        self.log = []

    def cursor(self):
        return self

    def execute(self, statement):
        self.log.append(("execute", statement))

    def executemany(self, statement, rows):
        self.log.append(("executemany", statement, len(rows)))

    def commit(self):
        self.log.append(("commit",))


def run():
    connection = Recorder()
    users = user_region_rows("example.onmicrosoft.com", "north.mgr:N,pricing.director:*")
    return connection.log, load(connection, generate(), users)


def test_users_commit_first_then_data_and_policy_in_one_transaction():
    log, _ = run()
    commits = [i for i, entry in enumerate(log) if entry == ("commit",)]
    assert len(commits) == 2 and commits[-1] == len(log) - 1
    before_first_commit = [entry[1] for entry in log[: commits[0]]]
    assert all("CREATE TABLE" not in s and "INSERT" not in s for s in before_first_commit)
    assert any("CREATE USER" in s for s in before_first_commit)


def test_policy_is_dropped_before_tables_and_recreated_after_rows():
    log, _ = run()
    statements = [entry[1] for entry in log if entry[0] != "commit"]
    drop_policy = statements.index("DROP SECURITY POLICY IF EXISTS rls.region_policy")
    first_create = next(i for i, s in enumerate(statements) if s.startswith("CREATE TABLE"))
    last_insert = max(i for i, s in enumerate(statements) if s.startswith("INSERT"))
    create_policy = next(
        i for i, s in enumerate(statements) if s.startswith("CREATE SECURITY POLICY")
    )
    assert drop_policy < first_create < last_insert < create_policy


def test_rows_are_inserted_in_chunks_and_counted():
    log, counts = run()
    sales = [
        entry[2] for entry in log if entry[0] == "executemany" and "dbo.fact_sales" in entry[1]
    ]
    assert max(sales) == CHUNK and sum(sales) == 98_460
    assert counts["fact_sales"] == 98_460 and counts["user_region"] == 2
