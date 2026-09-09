from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Set, Tuple

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "donantes_index.sqlite"
SOURCE_FILES = [
    ("actual", BASE_DIR / "GRUPO SANGRE.xlsx"),
    ("anterior", BASE_DIR / "DONANTESANT(1).xlsx"),
]

_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_OFFICE_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PACKAGE_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_COL_RE = re.compile(r"([A-Z]+)")

# Códigos observados en los dos sistemas. 9/10/11/0 no representan un grupo ABO/Rh utilizable.
GROUP_MAP = {
    "1": "A+",
    "2": "B+",
    "3": "AB+",
    "4": "O+",
    "5": "A-",
    "6": "B-",
    "7": "AB-",
    "8": "O-",
    "12": "B+",
}
GROUP_ORDER = {g: i for i, g in enumerate(("O+", "A+", "B+", "AB+", "O-", "A-", "B-", "AB-"))}


def normalize_ci(value: object) -> str:
    """Normaliza el carnet para búsquedas rápidas y tolerantes a espacios/puntos/guiones."""
    if value is None:
        return ""
    text = str(value).strip().upper()
    if text.endswith(".0") and text[:-2].replace(".", "").isdigit():
        text = text[:-2]
    # En las planillas el CI está almacenado principalmente como número. Se eliminan separadores visuales.
    text = re.sub(r"[^0-9A-Z]", "", text)
    return text


def _clean(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return re.sub(r"\s+", " ", text)


def _col_index(cell_ref: str) -> int:
    match = _COL_RE.match(cell_ref)
    if not match:
        return 0
    n = 0
    for char in match.group(1):
        n = n * 26 + ord(char) - 64
    return n - 1


def _sheet_path(zf: zipfile.ZipFile, sheet_name: str) -> str:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rel_map = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels.findall(_PACKAGE_REL + "Relationship")
    }
    sheets = workbook.find(_MAIN + "sheets")
    if sheets is None:
        raise KeyError(f"No hay hojas en {zf.filename}")
    for sheet in sheets:
        if sheet.attrib.get("name") == sheet_name:
            target = rel_map[sheet.attrib[_OFFICE_REL + "id"]]
            if target.startswith("/"):
                return target.lstrip("/")
            return "xl/" + target.lstrip("./")
    raise KeyError(f"No existe la hoja {sheet_name!r} en {zf.filename}")


def _shared_strings(zf: zipfile.ZipFile) -> List[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    result: List[str] = []
    with zf.open("xl/sharedStrings.xml") as fh:
        for _, elem in ET.iterparse(fh, events=("end",)):
            if elem.tag == _MAIN + "si":
                result.append("".join((node.text or "") for node in elem.iter(_MAIN + "t")))
                elem.clear()
    return result


def _read_cell(cell: ET.Element, shared: List[str]) -> str:
    cell_type = cell.attrib.get("t")
    value_node = cell.find(_MAIN + "v")
    if cell_type == "s" and value_node is not None and value_node.text:
        try:
            return shared[int(value_node.text)]
        except (ValueError, IndexError):
            return value_node.text
    if cell_type == "inlineStr":
        inline = cell.find(_MAIN + "is")
        if inline is not None:
            return "".join((node.text or "") for node in inline.iter(_MAIN + "t"))
        return ""
    if value_node is not None:
        return value_node.text or ""
    return ""


def iter_sheet_rows(path: Path, sheet_name: str) -> Iterator[Dict[int, str]]:
    """Lee XLSX en streaming usando solo XML estándar; evita cargar hojas completas en memoria."""
    with zipfile.ZipFile(path) as zf:
        shared = _shared_strings(zf)
        sheet_xml = _sheet_path(zf, sheet_name)
        with zf.open(sheet_xml) as fh:
            for _, elem in ET.iterparse(fh, events=("end",)):
                if elem.tag != _MAIN + "row":
                    continue
                row: Dict[int, str] = {}
                for cell in elem.findall(_MAIN + "c"):
                    row[_col_index(cell.attrib.get("r", "A1"))] = _read_cell(cell, shared)
                yield row
                elem.clear()


def _header_map(header_row: Dict[int, str]) -> Dict[str, int]:
    return {_clean(value): col for col, value in header_row.items() if _clean(value)}


def _source_digest() -> str:
    hasher = hashlib.sha256()
    for label, path in SOURCE_FILES:
        hasher.update(label.encode("utf-8"))
        hasher.update(path.name.encode("utf-8"))
        if not path.exists():
            hasher.update(b"MISSING")
            continue
        with path.open("rb") as fh:
            for block in iter(lambda: fh.read(1024 * 1024), b""):
                hasher.update(block)
    return hasher.hexdigest()


def index_is_current() -> bool:
    if not DB_PATH.exists():
        return False
    try:
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute("SELECT value FROM meta WHERE key='source_sha256'").fetchone()
        return bool(row and row[0] == _source_digest())
    except sqlite3.Error:
        return False


def _to_float(value: object) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return float("-inf")


def build_index(force: bool = False) -> Path:
    """Construye un índice SQLite unificado a partir de vamDonante y vamScreeni de ambos archivos."""
    missing = [str(path.name) for _, path in SOURCE_FILES if not path.exists()]
    if missing:
        raise FileNotFoundError("Faltan archivos fuente: " + ", ".join(missing))

    if not force and index_is_current():
        return DB_PATH

    # source -> CI -> lista de registros de donante
    donors: Dict[str, Dict[str, List[Dict[str, str]]]] = {}
    # source -> código donante -> CIs asociados (por robustez ante datos repetidos)
    code_to_cis: Dict[str, Dict[str, Set[str]]] = {}
    # source -> código -> fecha más reciente registrada
    code_latest: Dict[str, Dict[str, float]] = {}

    # CI -> grupo -> conteo / última fecha. Se combinan TODAS las donaciones de ambos sistemas.
    group_counts: Dict[str, Counter] = defaultdict(Counter)
    group_latest: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(lambda: float("-inf")))

    for source, path in SOURCE_FILES:
        by_ci: Dict[str, List[Dict[str, str]]] = defaultdict(list)
        by_code: Dict[str, Set[str]] = defaultdict(set)

        rows = iter_sheet_rows(path, "vamDonante")
        header = _header_map(next(rows))
        required = ("vdonCodDon", "vdonDocIde", "vdonNombre", "vdonPatern", "vdonMatern")
        absent = [name for name in required if name not in header]
        if absent:
            raise KeyError(f"Faltan columnas en {path.name}/vamDonante: {', '.join(absent)}")

        for row in rows:
            ci = normalize_ci(row.get(header["vdonDocIde"], ""))
            code = _clean(row.get(header["vdonCodDon"], ""))
            if not ci or not code:
                continue
            record = {
                "code": code,
                "nombre": _clean(row.get(header["vdonNombre"], "")),
                "paterno": _clean(row.get(header["vdonPatern"], "")),
                "materno": _clean(row.get(header["vdonMatern"], "")),
            }
            by_ci[ci].append(record)
            by_code[code].add(ci)

        donors[source] = by_ci
        code_to_cis[source] = by_code

        latest_for_code: Dict[str, float] = defaultdict(lambda: float("-inf"))
        rows = iter_sheet_rows(path, "vamScreeni")
        header = _header_map(next(rows))
        required = ("vdonCodDon", "vscrGrsCon", "vscrFechas")
        absent = [name for name in required if name not in header]
        if absent:
            raise KeyError(f"Faltan columnas en {path.name}/vamScreeni: {', '.join(absent)}")

        for row in rows:
            code = _clean(row.get(header["vdonCodDon"], ""))
            if not code:
                continue
            date_num = _to_float(row.get(header["vscrFechas"], ""))
            if date_num > latest_for_code[code]:
                latest_for_code[code] = date_num

            raw_group = _clean(row.get(header["vscrGrsCon"], ""))
            group = GROUP_MAP.get(raw_group)
            if not group:
                continue
            cis = by_code.get(code)
            if not cis:
                continue
            for ci in cis:
                group_counts[ci][group] += 1
                if date_num > group_latest[ci][group]:
                    group_latest[ci][group] = date_num

        code_latest[source] = latest_for_code

    all_cis = set()
    for source in donors:
        all_cis.update(donors[source].keys())

    def choose_record(ci: str) -> Tuple[str, str, str, str, str, str]:
        # Se prioriza el sistema actual. Si hay más de un código para un mismo CI,
        # se toma el que tenga la donación más reciente dentro de ese sistema.
        chosen_source = "actual" if donors.get("actual", {}).get(ci) else "anterior"
        records = donors.get(chosen_source, {}).get(ci, [])
        if not records:
            return "", "", "", "", "", ""
        latest_map = code_latest.get(chosen_source, {})
        record = max(records, key=lambda r: (latest_map.get(r["code"], float("-inf")), r["code"]))

        # Completa nombres faltantes desde el otro sistema sin reemplazar datos actuales válidos.
        nombre, paterno, materno = record["nombre"], record["paterno"], record["materno"]
        other_source = "anterior" if chosen_source == "actual" else "actual"
        other_records = donors.get(other_source, {}).get(ci, [])
        if other_records and (not nombre or not paterno or not materno):
            other = max(
                other_records,
                key=lambda r: (code_latest.get(other_source, {}).get(r["code"], float("-inf")), r["code"]),
            )
            nombre = nombre or other["nombre"]
            paterno = paterno or other["paterno"]
            materno = materno or other["materno"]

        actual_codes = donors.get("actual", {}).get(ci, [])
        old_codes = donors.get("anterior", {}).get(ci, [])
        code_actual = ""
        code_old = ""
        if actual_codes:
            code_actual = max(actual_codes, key=lambda r: (code_latest["actual"].get(r["code"], float("-inf")), r["code"]))["code"]
        if old_codes:
            code_old = max(old_codes, key=lambda r: (code_latest["anterior"].get(r["code"], float("-inf")), r["code"]))["code"]
        display_code = code_actual or code_old
        return nombre, paterno, materno, display_code, code_actual, code_old

    records_to_insert = []
    conflict_count = 0
    tie_count = 0
    no_group_count = 0

    for ci in sorted(all_cis):
        nombre, paterno, materno, display_code, code_actual, code_old = choose_record(ci)
        counts = group_counts.get(ci, Counter())
        group = ""
        winning_count = 0
        if counts:
            max_count = max(counts.values())
            candidates = [g for g, count in counts.items() if count == max_count]
            if len(counts) > 1:
                conflict_count += 1
            if len(candidates) > 1:
                tie_count += 1
            # Regla pedida: gana el grupo que más se repite. En empate, el más reciente.
            group = max(
                candidates,
                key=lambda g: (group_latest[ci].get(g, float("-inf")), -GROUP_ORDER.get(g, 999)),
            )
            winning_count = counts[group]
        else:
            no_group_count += 1

        full_name = " ".join(part for part in (nombre, paterno, materno) if part).strip()
        records_to_insert.append(
            (
                ci,
                full_name,
                nombre,
                paterno,
                materno,
                display_code,
                code_actual,
                code_old,
                group,
                winning_count,
                sum(counts.values()),
                json.dumps(dict(counts), ensure_ascii=False, sort_keys=True),
            )
        )

    tmp_path = DB_PATH.with_suffix(".sqlite.tmp")
    if tmp_path.exists():
        tmp_path.unlink()
    with sqlite3.connect(tmp_path) as conn:
        conn.execute("PRAGMA journal_mode=OFF")
        conn.execute("PRAGMA synchronous=OFF")
        conn.executescript(
            """
            CREATE TABLE donor_lookup (
                ci TEXT PRIMARY KEY,
                full_name TEXT NOT NULL,
                nombre TEXT,
                paterno TEXT,
                materno TEXT,
                codigo TEXT,
                codigo_actual TEXT,
                codigo_anterior TEXT,
                grupo TEXT,
                grupo_repeticiones INTEGER NOT NULL DEFAULT 0,
                grupos_validos INTEGER NOT NULL DEFAULT 0,
                grupos_detalle TEXT
            );
            CREATE TABLE meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        conn.executemany(
            """
            INSERT INTO donor_lookup (
                ci, full_name, nombre, paterno, materno, codigo,
                codigo_actual, codigo_anterior, grupo,
                grupo_repeticiones, grupos_validos, grupos_detalle
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            records_to_insert,
        )
        meta = {
            "source_sha256": _source_digest(),
            "total_donantes": str(len(records_to_insert)),
            "conflictos_grupo": str(conflict_count),
            "empates_resueltos_por_fecha": str(tie_count),
            "sin_grupo_valido": str(no_group_count),
        }
        conn.executemany("INSERT INTO meta(key, value) VALUES (?, ?)", meta.items())
        conn.commit()
        conn.execute("VACUUM")

    os.replace(tmp_path, DB_PATH)
    return DB_PATH


if __name__ == "__main__":
    path = build_index(force=True)
    with sqlite3.connect(path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM donor_lookup").fetchone()[0]
        with_group = conn.execute("SELECT COUNT(*) FROM donor_lookup WHERE grupo <> ''").fetchone()[0]
        meta = dict(conn.execute("SELECT key, value FROM meta"))
    print(f"Índice creado: {path}")
    print(f"Donantes: {total:,} | con grupo: {with_group:,}")
    print(json.dumps(meta, indent=2, ensure_ascii=False))
