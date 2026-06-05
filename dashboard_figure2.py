
from pathlib import Path
import zipfile, xml.etree.ElementTree as ET, re
import pandas as pd

NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

def col_to_num(col: str) -> int:
    n = 0
    for c in col:
        n = n * 26 + ord(c) - 64
    return n

def num_to_col(n: int) -> str:
    s = ""
    while n:
        n, rem = divmod(n - 1, 26)
        s = chr(65 + rem) + s
    return s

def ref_to_rc(ref: str) -> tuple[int, int]:
    m = re.match(r"([A-Z]+)([0-9]+)", ref)
    return int(m.group(2)), col_to_num(m.group(1))

class XlsmXmlReader:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.zip = zipfile.ZipFile(self.path)
        self.shared_strings = self._load_shared_strings()
        self.sheets = self._load_sheet_paths()
        self._values_cache = {}

    def _load_shared_strings(self):
        if "xl/sharedStrings.xml" not in self.zip.namelist():
            return []
        root = ET.fromstring(self.zip.read("xl/sharedStrings.xml"))
        out = []
        for si in root.findall("m:si", NS):
            out.append("".join(t.text or "" for t in si.findall(".//m:t", NS)))
        return out

    def _load_sheet_paths(self):
        wb = ET.fromstring(self.zip.read("xl/workbook.xml"))
        rels = ET.fromstring(self.zip.read("xl/_rels/workbook.xml.rels"))
        rid_to_target = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
        sheets = {}
        for sh in wb.find("m:sheets", NS):
            rid = sh.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            sheets[sh.attrib["name"]] = "xl/" + rid_to_target[rid]
        return sheets

    def sheet_names(self):
        return list(self.sheets.keys())

    def values(self, sheet_name: str):
        if sheet_name in self._values_cache:
            return self._values_cache[sheet_name]
        ws = ET.fromstring(self.zip.read(self.sheets[sheet_name]))
        vals = {}
        formulas = {}
        maxr = 0
        maxc = 0
        for cell in ws.findall(".//m:c", NS):
            ref = cell.attrib.get("r")
            if not ref:
                continue
            r, c = ref_to_rc(ref)
            maxr = max(maxr, r)
            maxc = max(maxc, c)
            v = cell.find("m:v", NS)
            f = cell.find("m:f", NS)
            val = None
            if v is not None:
                raw = v.text
                typ = cell.attrib.get("t")
                if typ == "s":
                    val = self.shared_strings[int(raw)]
                else:
                    try:
                        val = float(raw)
                    except Exception:
                        val = raw
            if f is not None:
                formulas[(r, c)] = f.text
            vals[(r, c)] = val
        result = (vals, formulas, maxr, maxc)
        self._values_cache[sheet_name] = result
        return result

    def cell(self, sheet_name: str, ref: str):
        vals, _, _, _ = self.values(sheet_name)
        return vals.get(ref_to_rc(ref))
