"""The pricing policy corpus (policies/*.md) and its AI Search index (D-009, D-036): one search
document per clause, carrying the Entra group IDs allowed to read it."""

import re
import time
from dataclasses import dataclass
from pathlib import Path

from azure.core.credentials import AccessToken
from azure.search.documents.indexes.models import (
    LexicalAnalyzerName,
    SearchableField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
)

from riad_data import settings

POLICIES_DIR = Path(__file__).resolve().parents[2] / "policies"
INDEX = "policies"
SCOPE = "https://search.azure.com/.default"


@dataclass(frozen=True)
class Clause:
    id: str
    doc_id: str
    title: str
    section: str
    citation: str
    content: str
    audience: tuple[str, ...]


def parse(path: Path) -> list[Clause]:
    """`## §N Title` is a clause, unless `### N.M` sub-clauses follow; then each is one, under
    the parent's title. Front matter: id, title, audience (comma-separated)."""
    _, front, body = path.read_text().split("---\n", 2)
    meta = dict(line.split(": ", 1) for line in front.strip().splitlines())
    doc_id, title = meta["id"], meta["title"]
    audience = tuple(name.strip() for name in meta["audience"].split(","))
    clauses = []
    for block in re.split(r"^## ", body, flags=re.M)[1:]:
        heading, _, rest = block.partition("\n")
        number, _, name = heading.partition(" ")
        number = number.removeprefix("§")
        intro, *subs = re.split(r"^### ", rest, flags=re.M)
        if subs and intro.strip():
            raise ValueError(f"{doc_id} §{number}: text before its sub-clauses")
        parts = [sub.split("\n", 1) for sub in subs] or [[number, intro]]
        for section, text in parts:
            section = section.strip()
            if not (section == number or section.startswith(f"{number}.")):
                raise ValueError(f"{doc_id} §{section} sits under §{number}")
            clauses.append(
                Clause(
                    id=f"{doc_id}_{section.replace('.', '-')}",
                    doc_id=doc_id,
                    title=title,
                    section=section,
                    citation=f"{doc_id} §{section}",
                    content=f"{name}. {text.strip()}",
                    audience=audience,
                )
            )
    return clauses


def load_corpus(directory: Path = POLICIES_DIR) -> list[Clause]:
    return [clause for path in sorted(directory.glob("*.md")) for clause in parse(path)]


def documents(clauses: list[Clause], groups: dict[str, str]) -> list[dict]:
    docs = []
    for clause in clauses:
        unknown = [name for name in clause.audience if name not in groups]
        if unknown:
            raise ValueError(f"{clause.citation}: unknown audience {', '.join(unknown)}")
        docs.append(
            {
                "id": clause.id,
                "doc_id": clause.doc_id,
                "title": clause.title,
                "section": clause.section,
                "citation": clause.citation,
                "content": clause.content,
                "group_ids": [groups[name] for name in clause.audience],
                "is_fixture": False,
            }
        )
    return docs


def index_definition() -> SearchIndex:
    text = SearchFieldDataType.STRING
    return SearchIndex(
        name=INDEX,
        fields=[
            SimpleField(name="id", type=text, key=True),
            *(SimpleField(name=n, type=text, filterable=True) for n in ("doc_id", "section")),
            SimpleField(name="title", type=text),
            SimpleField(name="citation", type=text, filterable=True),
            SearchableField(name="content", analyzer_name=LexicalAnalyzerName.EN_MICROSOFT),
            SimpleField(
                name="group_ids", type=SearchFieldDataType.Collection(text), filterable=True
            ),
            SimpleField(name="is_fixture", type=SearchFieldDataType.BOOLEAN, filterable=True),
        ],
    )


def sync(index_client, search_client, docs: list[dict]) -> tuple[int, int]:
    """Creates or updates the index, uploads the corpus and removes clauses no longer in it."""
    index_client.create_or_update_index(index_definition())
    existing = {hit["id"] for hit in search_client.search(search_text="*", select=["id"], top=1000)}
    stale = sorted(existing - {doc["id"] for doc in docs})
    search_client.merge_or_upload_documents(documents=docs)
    if stale:
        search_client.delete_documents(documents=[{"id": doc_id} for doc_id in stale])
    return len(docs), len(stale)


def policy_groups(values: dict[str, str]) -> dict[str, str]:
    (raw,) = settings.require(values, "POLICY_GROUPS")
    pairs = (item.split(":", 1) for item in raw.split(",") if item.strip())
    return {name.strip(): group_id.strip() for name, group_id in pairs}


class StaticToken:
    """An azure-core credential over one interactive sign-in; the script runs for seconds."""

    def __init__(self, token: str) -> None:
        self._token = AccessToken(token, int(time.time()) + 3000)

    def get_token(self, *scopes: str, **kwargs) -> AccessToken:
        return self._token
