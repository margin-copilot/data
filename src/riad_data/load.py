"""Loads the dataset into Azure SQL. Users and the reader role first, then one transaction for
tables, rows and the security policy: other sessions wait on it, so a reload never exposes
unfiltered rows."""

from riad_data import rls, tables
from riad_data.generate import Dataset

CHUNK = 1000


def load(connection, data: Dataset, user_region: list[dict]) -> dict[str, int]:
    cursor = connection.cursor()
    for statement in rls.principal_statements([row["upn"] for row in user_region]):
        cursor.execute(statement)
    connection.commit()
    for statement in rls.drop_statements() + tables.create_statements():
        cursor.execute(statement)
    counts = {}
    for table, rows in [*data.tables.items(), ("user_region", user_region)]:
        values = tables.rows_for(table, rows)
        insert = tables.insert_statement(table)
        for start in range(0, len(values), CHUNK):
            cursor.executemany(insert, values[start : start + CHUNK])
        counts[table] = len(values)
    for statement in rls.policy_statements():
        cursor.execute(statement)
    connection.commit()
    return counts
