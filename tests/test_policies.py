import pytest

from riad_data.policies import documents, index_definition, load_corpus, policy_groups, sync

GROUPS = {"all": "A", "north": "N", "center": "C", "south": "S", "directors": "D"}
CITED = {
    "PP-01 §5",
    "PP-02 §1",
    "PP-02 §2",
    "PP-02 §4",
    "PP-03 §2.1",
    "PP-03 §2.3",
    "PP-04 §2.2",
    "PP-04 §3.2",
    "PP-04 §3.4",
    "PP-04 §4",
    "PP-05-N §2",
    "PP-05-N §3",
    "PP-06 §1",
    "PP-07 §2",
}


def test_the_corpus_has_46_clauses():
    assert len(load_corpus()) == 46


def test_the_cited_clauses_exist():
    assert CITED <= {clause.citation for clause in load_corpus()}


def test_a_sub_clause_carries_its_parent_title():
    clause = next(c for c in load_corpus() if c.citation == "PP-04 §3.2")
    assert clause.id == "PP-04_3-2"
    assert clause.content.startswith("Limits per increase. Tier B:")
    assert "up to 4%" in clause.content


def test_restricted_documents_carry_only_their_groups():
    docs = documents(load_corpus(), GROUPS)
    by_doc = {}
    for doc in docs:
        by_doc.setdefault(doc["doc_id"], set()).add(tuple(doc["group_ids"]))
    assert by_doc["PP-06"] == {("D",)}
    assert by_doc["PP-05-N"] == {("N", "D")}
    assert by_doc["PP-04"] == {("A",)}
    assert all(doc["is_fixture"] is False for doc in docs)


def test_an_unknown_audience_is_rejected(tmp_path):
    (tmp_path / "PP-99.md").write_text(
        "---\nid: PP-99\ntitle: Test\naudience: everyone\n---\n\n## §1 Scope\nText.\n"
    )
    with pytest.raises(ValueError, match="everyone"):
        documents(load_corpus(tmp_path), GROUPS)


def test_index_fields():
    fields = {field.name: field for field in index_definition().fields}
    assert set(fields) == {
        "id",
        "doc_id",
        "title",
        "section",
        "citation",
        "content",
        "group_ids",
        "is_fixture",
    }
    assert fields["id"].key
    assert fields["group_ids"].filterable and fields["is_fixture"].filterable
    assert fields["content"].searchable and fields["content"].analyzer_name == "en.microsoft"


class FakeIndexClient:
    def __init__(self):
        self.indexes = []

    def create_or_update_index(self, index):
        self.indexes.append(index.name)


class FakeSearchClient:
    def __init__(self, existing):
        self.existing, self.uploaded, self.deleted = existing, [], []

    def search(self, search_text, select, top):
        return [{"id": doc_id} for doc_id in self.existing]

    def merge_or_upload_documents(self, documents):
        self.uploaded.extend(documents)

    def delete_documents(self, documents):
        self.deleted.extend(documents)


def test_sync_uploads_the_corpus_and_deletes_stale_documents():
    index_client, search_client = FakeIndexClient(), FakeSearchClient(["PP-99_1", "PP-04_1"])
    docs = documents(load_corpus(), GROUPS)
    assert sync(index_client, search_client, docs) == (46, 1)
    assert index_client.indexes == ["policies"]
    assert search_client.deleted == [{"id": "PP-99_1"}]


def test_policy_groups_setting_is_required_for_policies():
    with pytest.raises(SystemExit, match="POLICY_GROUPS"):
        policy_groups({})
    assert policy_groups({"POLICY_GROUPS": "all:A, directors:D"}) == {"all": "A", "directors": "D"}
