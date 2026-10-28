"""Read raw sources without modifying them, cast to canonical schemas, log every change.

Rules
- Raw files are opened read-only; the ANP CSVs are read straight from the ZIP.
- Everything is first read as text (no type inference), then cast explicitly.
- Every row keeps provenance: src_file, src_member/src_sheet, src_row (line/row number in the source).
- Whitespace normalisation is logged cell by cell; the original text is never lost.
- A value that cannot be cast is never coerced silently: it is reported as an ERROR.
"""
from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd

from .qc import QCRegistry
from .schemas import ANP_TABLES, CATEGORIES

PROV = ["src_file", "src_member", "src_row"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(raw_dir: Path, sources: dict, qc: QCRegistry) -> pd.DataFrame:
    rows = []
    for key, s in sources.items():
        p = raw_dir / s["file"]
        if not p.exists():
            qc.add(f"source.exists.{key}", "source", "ERROR", f"Missing raw file {s['file']}")
            continue
        got = sha256(p)
        ok = got == s["sha256"]
        qc.add(f"source.sha256.{key}", "source", "PASS" if ok else "ERROR",
               f"{s['file']}: SHA-256 {'matches' if ok else 'DOES NOT MATCH'} the locked value",
               0 if ok else 1, "" if ok else f"expected {s['sha256']} got {got}")
        rows.append({"source_key": key, **{k: s[k] for k in ("file", "publisher", "title", "version", "date")},
                     "sha256": got, "bytes": p.stat().st_size, "sha256_matches_lock": ok})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- readers
def read_anp_member(zip_path: Path, member: str) -> pd.DataFrame:
    with zipfile.ZipFile(zip_path) as z:
        raw = z.read(member)
    text = raw.decode("utf-8")  # verified: all members are valid UTF-8, no BOM
    df = pd.read_csv(io.StringIO(text), sep=";", dtype=str, keep_default_na=False, na_filter=False)
    df.insert(0, "src_row", np.arange(2, len(df) + 2))  # line number in the CSV (header = line 1)
    df.insert(0, "src_member", member)
    df.insert(0, "src_file", zip_path.name)
    return df


def read_xlsx_sheet(path: Path, sheet: str, header_row: int = 1) -> pd.DataFrame:
    """Read one sheet with cell values as stored (numbers stay numbers). Read-only."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb[sheet]
        rows = list(ws.iter_rows(values_only=True))
    finally:
        wb.close()
    header = [str(h).strip() if h is not None else f"_col{i}" for i, h in enumerate(rows[header_row - 1])]
    data, src_rows = [], []
    for i, r in enumerate(rows[header_row:], start=header_row + 1):
        if r is None or all(c is None for c in r):
            continue
        data.append(list(r) + [None] * (len(header) - len(r)))
        src_rows.append(i)
    df = pd.DataFrame(data, columns=header)
    # drop header-less columns that are completely empty (spreadsheet formatting artefacts)
    df = df.drop(columns=[c for c in df.columns if c.startswith("_col") and df[c].isna().all()])
    df.insert(0, "src_row", src_rows)
    df.insert(0, "src_member", sheet)
    df.insert(0, "src_file", path.name)
    return df


# --------------------------------------------------------------------------- casting
def cast_anp_table(name: str, raw: pd.DataFrame, qc: QCRegistry, norm_log: list) -> pd.DataFrame:
    spec = ANP_TABLES[name]
    expected = [c[0] for c in spec["columns"]]
    missing = [c for c in expected if c not in raw.columns]
    extra = [c for c in raw.columns if c not in expected + PROV]
    qc.check(f"structure.columns.{name}", "structure", len(missing),
             f"{name}: all {len(expected)} expected columns present",
             f"{name}: missing columns {missing}")
    if extra:
        qc.add(f"structure.extra_columns.{name}", "structure", "WARNING", f"{name}: unexpected columns {extra}", len(extra))

    out = raw[PROV].copy()
    bad_cast = 0
    for src, canon, kind, unit, _desc in spec["columns"]:
        s = raw[src].astype(str)
        stripped = s.str.strip()
        changed = s != stripped
        for idx in np.flatnonzero(changed.to_numpy()):
            norm_log.append({"table": name, "column": canon, "src_file": raw["src_file"].iat[idx],
                             "src_member": raw["src_member"].iat[idx], "src_row": int(raw["src_row"].iat[idx]),
                             "original": s.iat[idx], "normalised": stripped.iat[idx], "rule": "strip_whitespace"})
        val = stripped.replace("", pd.NA)
        if kind in ("id", "cat", "str"):
            out[canon] = val.astype("string")
        else:
            num = pd.to_numeric(val, errors="coerce")
            failed = val.notna() & num.isna()
            if failed.any():
                bad_cast += int(failed.sum())
                qc.add(f"structure.cast.{name}.{canon}", "structure", "ERROR",
                       f"{name}.{canon}: {int(failed.sum())} values not numeric", int(failed.sum()),
                       f"examples: {val[failed].head(5).tolist()}")
            if kind == "int":
                if (num.dropna() % 1 != 0).any():
                    qc.add(f"structure.int.{name}.{canon}", "structure", "ERROR",
                           f"{name}.{canon}: non-integer values in an integer column")
                out[canon] = num.astype("Int64")
            else:
                out[canon] = num.astype("float64")
    if bad_cast == 0:
        qc.add(f"structure.cast.{name}", "structure", "PASS", f"{name}: every value cast to its declared type")

    n_changed = sum(1 for r in norm_log if r["table"] == name)
    qc.add(f"normalisation.whitespace.{name}", "normalisation", "INFO" if n_changed else "PASS",
           f"{name}: {n_changed} cells had leading/trailing whitespace removed (logged)" if n_changed
           else f"{name}: no whitespace normalisation needed", n_changed)

    for (tbl, col), allowed in CATEGORIES.items():
        if tbl != name:
            continue
        bad = out[col].dropna()[~out[col].dropna().isin(allowed)]
        qc.check(f"structure.category.{name}.{col}", "structure", len(bad),
                 f"{name}.{col}: all values in controlled vocabulary",
                 f"{name}.{col}: values outside vocabulary", details=str(sorted(set(bad))[:10]))

    key = spec["key"]
    dup = out.duplicated(key, keep=False)
    qc.check(f"structure.key_unique.{name}", "structure", int(dup.sum()),
             f"{name}: primary key {key} unique after normalisation",
             f"{name}: duplicate primary keys", details=str(out.loc[dup, key].head(5).values.tolist()))
    qc.add(f"structure.rows.{name}", "structure", "INFO", f"{name}: {len(out)} rows", len(out))
    return out
