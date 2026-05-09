"""In-memory Supabase shim — supports the small chained query surface
used by the adherence/therapy-data services. Not a full Supabase
client mock; just enough to drive tests deterministically without a
real DB.

Supports::

    .table(name).select(cols).eq(col, val).execute()
    .in_(col, list)  .gte/.lte/.lt/.gt(col, val)
    .order(col, desc=...)  .range(a, b)  .limit(n)
    .not_.is_(col, "null")
    .insert(payload).execute()
    .update(payload).eq(col, val).execute()
    .delete().eq(col, val).execute()

Plus the foreign-key dot-syntax used in nested selects:
    select("*, profiles!inner(user_id)")
We honour the !inner join: any row whose foreign profile matches the
filter is returned, with the joined object embedded as
``row["profiles"] = {"user_id": ...}``.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


# ---------------------------------------------------------------------------
# Result wrapper
# ---------------------------------------------------------------------------
class _Result:
    def __init__(self, data: list[dict[str, Any]]):
        self.data = data


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------
class _Query:
    def __init__(
        self,
        client: "FakeSupabase",
        table_name: str,
        *,
        op: str = "select",
        select_arg: str = "*",
        payload: dict | None = None,
    ):
        self._client = client
        self._table_name = table_name
        self._op = op
        self._select = select_arg
        self._payload = payload or {}
        self._filters: list[tuple[str, str, Any]] = []
        self._order_by: tuple[str, bool] | None = None
        self._range: tuple[int, int] | None = None
        self._limit: int | None = None

    # -------- chained verbs --------
    def select(self, cols: str = "*") -> "_Query":
        self._op = "select"
        self._select = cols
        return self

    def insert(self, payload: dict) -> "_Query":
        self._op = "insert"
        self._payload = dict(payload)
        return self

    def update(self, payload: dict) -> "_Query":
        self._op = "update"
        self._payload = dict(payload)
        return self

    def delete(self) -> "_Query":
        self._op = "delete"
        return self

    # -------- filters --------
    def eq(self, col: str, val: Any) -> "_Query":
        self._filters.append(("eq", col, val))
        return self

    def in_(self, col: str, vals: list[Any]) -> "_Query":
        self._filters.append(("in", col, list(vals)))
        return self

    def gte(self, col: str, val: Any) -> "_Query":
        self._filters.append(("gte", col, val))
        return self

    def lte(self, col: str, val: Any) -> "_Query":
        self._filters.append(("lte", col, val))
        return self

    def gt(self, col: str, val: Any) -> "_Query":
        self._filters.append(("gt", col, val))
        return self

    def lt(self, col: str, val: Any) -> "_Query":
        self._filters.append(("lt", col, val))
        return self

    @property
    def not_(self) -> "_NotChain":
        return _NotChain(self)

    def order(self, col: str, desc: bool = False) -> "_Query":
        self._order_by = (col, desc)
        return self

    def range(self, start: int, end: int) -> "_Query":
        self._range = (start, end)
        return self

    def limit(self, n: int) -> "_Query":
        self._limit = n
        return self

    # -------- terminal --------
    def execute(self) -> _Result:
        if self._op == "select":
            return self._do_select()
        if self._op == "insert":
            return self._do_insert()
        if self._op == "update":
            return self._do_update()
        if self._op == "delete":
            return self._do_delete()
        raise ValueError(f"unknown op: {self._op}")

    # -------- impls --------
    def _do_select(self) -> _Result:
        rows = self._client._tables.get(self._table_name, [])
        out: list[dict[str, Any]] = []
        for row in rows:
            if not self._matches(row):
                continue
            out.append(self._project(row))
        if self._order_by is not None:
            col, desc = self._order_by
            out.sort(key=lambda r: (r.get(col) is None, r.get(col)), reverse=desc)
        if self._range is not None:
            a, b = self._range
            out = out[a : b + 1]
        elif self._limit is not None:
            out = out[: self._limit]
        return _Result(deepcopy(out))

    def _do_insert(self) -> _Result:
        rows = self._client._tables.setdefault(self._table_name, [])
        row = dict(self._payload)
        row.setdefault("id", self._client._next_id(self._table_name))
        rows.append(deepcopy(row))
        return _Result([deepcopy(row)])

    def _do_update(self) -> _Result:
        rows = self._client._tables.get(self._table_name, [])
        updated = []
        for r in rows:
            if self._matches(r):
                r.update(deepcopy(self._payload))
                updated.append(deepcopy(r))
        return _Result(updated)

    def _do_delete(self) -> _Result:
        rows = self._client._tables.get(self._table_name, [])
        kept, removed = [], []
        for r in rows:
            if self._matches(r):
                removed.append(deepcopy(r))
            else:
                kept.append(r)
        self._client._tables[self._table_name] = kept
        return _Result(removed)

    # -------- internals --------
    def _matches(self, row: dict[str, Any]) -> bool:
        for op, col, val in self._filters:
            row_val = row.get(col)
            if op == "eq" and row_val != val:
                return False
            if op == "in" and row_val not in val:
                return False
            if op == "gte" and (row_val is None or _cmp(row_val, val) < 0):
                return False
            if op == "lte" and (row_val is None or _cmp(row_val, val) > 0):
                return False
            if op == "gt" and (row_val is None or _cmp(row_val, val) <= 0):
                return False
            if op == "lt" and (row_val is None or _cmp(row_val, val) >= 0):
                return False
            if op == "not_is_null" and row_val is None:
                return False
        # FK !inner filter via select arg: parse "*, profiles!inner(user_id)"
        for fk_table, fk_cols in _parse_fk_inner(self._select):
            fk_col = f"{_singular(fk_table)}_id"
            fk_id = row.get(fk_col)
            if fk_id is None:
                return False
            joined = self._client._find_by_id(fk_table, fk_id)
            if joined is None:
                return False
        return True

    def _project(self, row: dict[str, Any]) -> dict[str, Any]:
        # If select includes nested "table!inner(cols)", attach the joined obj.
        if self._select.strip() == "*":
            return dict(row)
        out = dict(row)
        for fk_table, fk_cols in _parse_fk_inner(self._select):
            fk_col = f"{_singular(fk_table)}_id"
            fk_id = row.get(fk_col)
            joined = self._client._find_by_id(fk_table, fk_id)
            if joined is not None:
                out[fk_table] = {c: joined.get(c) for c in fk_cols}
        # Plain comma-separated columns: project subset; we keep all.
        return out


# ---------------------------------------------------------------------------
# .not_ chain
# ---------------------------------------------------------------------------
class _NotChain:
    def __init__(self, q: _Query):
        self._q = q

    def is_(self, col: str, val: str) -> _Query:
        if val == "null":
            self._q._filters.append(("not_is_null", col, None))
        return self._q


# ---------------------------------------------------------------------------
# Fake client
# ---------------------------------------------------------------------------
class FakeSupabase:
    """Minimal in-memory Supabase replacement for unit tests."""

    def __init__(self, seed: dict[str, list[dict[str, Any]]] | None = None):
        self._tables: dict[str, list[dict[str, Any]]] = {}
        if seed:
            for name, rows in seed.items():
                self._tables[name] = [deepcopy(r) for r in rows]
        self._counters: dict[str, int] = {}

    def table(self, name: str) -> _Query:
        return _Query(self, name)

    # called by _Query helpers
    def _find_by_id(self, table: str, fk_id: Any) -> dict[str, Any] | None:
        for r in self._tables.get(table, []):
            if r.get("id") == fk_id:
                return r
        return None

    def _next_id(self, table: str) -> str:
        self._counters[table] = self._counters.get(table, 0) + 1
        return f"{table}-auto-{self._counters[table]}"

    # convenience for tests
    def insert_rows(self, table: str, rows: list[dict[str, Any]]) -> None:
        self._tables.setdefault(table, []).extend(deepcopy(rows))


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _cmp(a: Any, b: Any) -> int:
    # Compare strings/dates/ints by Python natural order. ISO date/datetime
    # strings sort correctly lexicographically.
    if a == b:
        return 0
    return -1 if a < b else 1


def _singular(name: str) -> str:
    # crude pluralisation reverse — good enough for our table names
    if name.endswith("ies"):
        return name[:-3] + "y"
    if name.endswith("s"):
        return name[:-1]
    return name


def _parse_fk_inner(select_arg: str) -> list[tuple[str, list[str]]]:
    """Parse "*, profiles!inner(user_id), x(y,z)" → [("profiles",["user_id"]),
    ("x",["y","z"])]. Only !inner is treated as a join filter; plain
    nested selects (medications(name)) just extract data without
    filtering.
    """
    out = []
    s = select_arg
    while True:
        i = s.find("(")
        if i < 0:
            break
        j = s.find(")", i)
        if j < 0:
            break
        head = s[:i].strip().rstrip(",").strip()
        # find table name token (last identifier in head)
        last_token = head.split(",")[-1].strip()
        is_inner = "!inner" in last_token
        table = last_token.replace("!inner", "").strip()
        cols = [c.strip() for c in s[i + 1 : j].split(",") if c.strip()]
        if is_inner:
            out.append((table, cols))
        s = s[j + 1 :]
    return out
