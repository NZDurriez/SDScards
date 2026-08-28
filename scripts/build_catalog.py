#!/usr/bin/env python3
"""Build sds-index.json, card thumbnails, and a zip of all Mini SDS PDFs."""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
MINIS = ROOT / "minis"
THUMBS = ROOT / "thumbs"
DATA = ROOT / "data"
ZIP_PATH = ROOT / "minis.zip"

H_LABELS = {
    "H222": "Extremely flammable aerosol",
    "H229": "Pressurised container: may burst if heated",
    "H222+H229": "Extremely flammable aerosol. May burst if heated",
    "H302": "Harmful if swallowed",
    "H304": "May be fatal if swallowed and enters airways",
    "H315": "Causes skin irritation",
    "H317": "May cause an allergic skin reaction",
    "H319": "Causes serious eye irritation",
    "H320": "Causes eye irritation",
    "H335": "May cause respiratory irritation",
    "H336": "May cause drowsiness or dizziness",
    "H351": "Suspected of causing cancer",
    "H360": "May damage fertility or the unborn child",
    "H361": "Suspected of damaging fertility or the unborn child",
    "H372": "Causes damage to organs through prolonged or repeated exposure",
    "H373": "May cause damage to organs through prolonged or repeated exposure",
    "H401": "Toxic to aquatic life",
    "H402": "Harmful to aquatic life",
    "H410": "Very toxic to aquatic life with long lasting effects",
    "H411": "Toxic to aquatic life with long lasting effects",
    "H412": "Harmful to aquatic life with long lasting effects",
}


def clean_filename(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"^MiniSDS_", "", stem)
    stem = re.sub(r"_undefined_AUS_EN$", "", stem)
    stem = re.sub(r"_\d{4}_[A-Za-z]+_\d+_AUS_EN$", "", stem)
    stem = stem.replace("__", " ").replace("_", " ")
    return re.sub(r"\s+", " ", stem).strip()


TITLE_OVERRIDES = {
    "MiniSDS_CRC 556 Marine Aerosol (NZ)_undefined_AUS_EN.pdf": "CRC 556 / 66-Marine (6006) Marine Aerosol",
    "CKL402 - Colorpak Lacquer Fillable Aerosol.pdf": "Colorpak Lacquer Fillable Aerosol (CFL402 / CKL402 Deep Bronze Green)",
    "692918 - RS Optical Instrument Cleaner (400ml).pdf": "RS PRO Optical Instrument Cleaner 692-918 (400ml aerosol)",
    "982085694 - RS Optical Instrument Cleaner (250ml).pdf": "RS PRO Optical Instrument Cleaner 136-8540 / 982085694 (250ml)",
    "739294 - SC Johnson Pledge Multi-Surface Aerosol (500g).pdf": "SC Johnson Professional Pledge Aerosol Multi-Surface Cleaner (UK)",
}


def brand_of(*parts: str) -> str:
    blob = " ".join(parts).lower()
    if "rs pro" in blob or "optical instrument cleaner" in blob:
        return "RS PRO"
    if "crc" in blob:
        return "CRC"
    if "damar" in blob:
        return "Damar"
    if "galmet" in blob:
        return "Galmet"
    if "colorpak" in blob or "formula" in blob:
        return "Colorpak"
    if "raid" in blob:
        return "Raid"
    if "wurth" in blob or "würth" in blob:
        return "Würth"
    if "inox" in blob:
        return "INOX"
    if "3m" in blob:
        return "3M"
    if "air wick" in blob or "airwick" in blob:
        return "Air Wick"
    if "pledge" in blob:
        return "Pledge"
    if "lowa" in blob:
        return "LOWA"
    return "Other"


def sku_from_filename(filename: str) -> str | None:
    stem = Path(filename).stem
    m = re.match(r"^([A-Za-z0-9.-]+)\s+-", stem)
    if m and any(ch.isdigit() for ch in m.group(1)):
        return m.group(1)
    cleaned = clean_filename(filename)
    m = re.search(r"\b(\d{3,7})\b", cleaned)
    return m.group(1) if m else None


def pack_size(filename: str) -> str | None:
    m = re.search(r"\(([^)]*\d+\s*(?:ml|g|kg|L)[^)]*)\)", filename, re.I)
    return m.group(1).strip() if m else None


def product_from_pdf(text: str) -> str | None:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for i, ln in enumerate(lines):
        upper = ln.upper()
        if "THIS IS A SUMMARY ONLY" not in upper and upper != "MINI SDS":
            continue
        for later in lines[i + 1 :]:
            u = later.upper()
            if "THIS IS A SUMMARY ONLY" in u or u == "MINI SDS":
                continue
            if u.startswith(("INGREDIENTS", "CAS NO", "CHEMWATCH", "UN NO")):
                break
            if len(later) > 2:
                return later
        break
    return None


def hazard_codes(text: str) -> list[str]:
    found = re.findall(r"\b(H\d{3}(?:\+H\d{3})?)\b", text)
    # Drop codes that are actually AUH044 / AUH066 fragments
    cleaned = []
    seen = set()
    for code in found:
        if code in {"H044", "H066"}:
            continue
        if code not in seen:
            seen.add(code)
            cleaned.append(code)
    return cleaned


def pictograms(codes: list[str]) -> list[str]:
    tags: list[str] = []

    def add(tag: str) -> None:
        if tag not in tags:
            tags.append(tag)

    joined = " ".join(codes)
    if any(c.startswith(("H220", "H222", "H224", "H225", "H226", "H228", "H229")) or "H222" in c for c in codes):
        add("flame")
    if any(c in {"H229"} or c.endswith("H229") for c in codes):
        add("gas")
    if any(c in {"H314", "H318"} for c in codes):
        add("corrosion")
    if any(c in {"H351", "H350", "H360", "H361", "H304", "H372", "H373"} for c in codes):
        add("health")
    if any(c.startswith("H4") for c in codes):
        add("environment")
    if any(c in {"H302", "H315", "H317", "H319", "H320", "H335", "H336"} for c in codes):
        add("exclamation")
    if "H222+H229" in joined:
        add("flame")
        add("gas")
    return tags


def extract_card(path: Path) -> dict:
    doc = pymupdf.open(path)
    page = doc[0]
    text = page.get_text()
    display = clean_filename(path.name)
    pdf_name = product_from_pdf(text)
    title = TITLE_OVERRIDES.get(path.name, display)
    if path.name not in TITLE_OVERRIDES and pdf_name:
        truncated = display.count("(") > display.count(")")
        if truncated or len(pdf_name) > len(display):
            title = pdf_name

    chemwatch = None
    m = re.search(r"Chemwatch:\s*([0-9-]+)", text)
    if m:
        chemwatch = m.group(1)

    alert = None
    m = re.search(r"Chemwatch Hazard Alert Code:\s*(\d+)", text)
    if m:
        alert = int(m.group(1))

    un_no = None
    m = re.search(r"UN(?:\s*No\.?|\s*number)?\s*:?\s*(1950|\d{4})", text, re.I)
    if m:
        un_no = m.group(1)

    dg = None
    m = re.search(r"DG Class:\s*([0-9.A-Za-z]+)", text)
    if not m:
        m = re.search(r"(?:hazard )?class(?:es)?\s*:?\s*(2\.[12])", text, re.I)
    if m:
        dg = m.group(1)

    signal = None
    m = re.search(r"Signal word:?\s*(Danger|Warning)", text, re.I)
    if m:
        signal = m.group(1).title()

    kind = "Mini SDS" if ("MINI SDS" in text.upper() or "THIS IS A SUMMARY ONLY" in text.upper()) else "Full SDS"

    codes = hazard_codes(text)
    hazards = [{"code": c, "label": H_LABELS.get(c, c)} for c in codes]

    thumb_name = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem)[:80] + ".jpg"
    thumb_path = THUMBS / thumb_name
    pix = page.get_pixmap(matrix=pymupdf.Matrix(0.7, 0.7), alpha=False)
    pix.save(thumb_path, jpg_quality=62)

    search = re.sub(r"\s+", " ", f"{display} {title} {pdf_name or ''} {text}").strip().lower()

    return {
        "id": re.sub(r"[^a-z0-9]+", "-", display.lower()).strip("-"),
        "file": path.name,
        "url": f"minis/{path.name}",
        "thumb": f"thumbs/{thumb_name}",
        "title": title,
        "product": pdf_name or title,
        "sku": sku_from_filename(path.name),
        "size": pack_size(path.name),
        "brand": brand_of(display, pdf_name or ""),
        "chemwatch": chemwatch,
        "hazardAlert": alert,
        "un": un_no,
        "dgClass": dg,
        "signal": signal,
        "hazards": hazards,
        "pictograms": pictograms(codes),
        "kind": kind,
        "bytes": path.stat().st_size,
        "pages": doc.page_count,
        "search": search,
    }


def main() -> None:
    THUMBS.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(MINIS.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDFs found in {MINIS}")

    cards = [extract_card(p) for p in pdfs]
    catalog = {
        "title": "Mini SDS Library",
        "source": "minis",
        "count": len(cards),
        "cards": cards,
    }
    (DATA / "sds-index.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_STORED) as zf:
        for p in pdfs:
            zf.write(p, arcname=p.name)

    print(f"Indexed {len(cards)} Mini SDS cards")
    print(f"Wrote {DATA / 'sds-index.json'}")
    print(f"Wrote {ZIP_PATH} ({ZIP_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
