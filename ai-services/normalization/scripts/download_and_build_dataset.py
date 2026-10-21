#!/usr/bin/env python3
"""
Full-Scale Reference Dataset Builder for Medication Name Normalizer.
Downloads and integrates:
1. OpenFDA NDC full database (120,000+ drug records)
2. RxNorm allconcepts API (all active concepts across clinical/branded drugs and ingredients)
Produces an indexed SQLite database in data/reference/drug_reference.sqlite
and structured CSV/Parquet summaries for high-speed profiling and evaluation corpus generation.
"""

import csv
import io
import json
import logging
import os
import sqlite3
import sys
import time
import zipfile
from pathlib import Path
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent  # ai-services/normalization
DATA_REF_DIR = BASE_DIR / "data" / "reference"
DATA_REF_DIR.mkdir(parents=True, exist_ok=True)

SQLITE_PATH = DATA_REF_DIR / "drug_reference.sqlite"
RXNORM_CONCEPTS_CSV = DATA_REF_DIR / "rxnorm_allconcepts.csv"
OPENFDA_NDC_CSV = DATA_REF_DIR / "openfda_ndc_products.csv"

OPENFDA_NDC_URL = "https://download.open.fda.gov/drug/ndc/drug-ndc-0001-of-0001.json.zip"
RXNORM_ALLCONCEPTS_URL = "https://rxnav.nlm.nih.gov/REST/allconcepts.json?tty=SCD+SBD+GPCK+BPCK+IN+PIN+MIN+BN"

GOOGLE_DRIVE_DATASET_URL = os.environ.get(
    "DRUG_REFERENCE_GDRIVE_URL",
    r"G:\My Drive\Modawem_RxNorm_Dataset"
)


def download_with_progress(url: str, dest_path: Path, max_retries: int = 3) -> None:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = dest_path.with_suffix(dest_path.suffix + ".tmp")
    
    headers = {"User-Agent": "Modawem-MedicationNormalizer/1.0 (Clinical Informatics Audit)"}
    for attempt in range(1, max_retries + 1):
        try:
            logging.info(f"Downloading {url} (Attempt {attempt}/{max_retries})...")
            req = Request(url, headers=headers)
            with urlopen(req, timeout=60) as resp, open(temp_path, "wb") as out_file:
                total_size = resp.getheader("Content-Length")
                total_size = int(total_size) if total_size else None
                downloaded = 0
                chunk_size = 1024 * 1024  # 1MB
                start_time = time.time()
                last_log = start_time

                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    downloaded += len(chunk)
                    now = time.time()
                    if now - last_log > 2.0:
                        speed = (downloaded / (now - start_time)) / (1024 * 1024)
                        if total_size:
                            pct = (downloaded / total_size) * 100
                            logging.info(f"Progress: {downloaded / (1024*1024):.1f}MB / {total_size / (1024*1024):.1f}MB ({pct:.1f}%) - {speed:.1f} MB/s")
                        else:
                            logging.info(f"Progress: {downloaded / (1024*1024):.1f}MB downloaded - {speed:.1f} MB/s")
                        last_log = now

            if temp_path.exists():
                if dest_path.exists():
                    dest_path.unlink()
                temp_path.rename(dest_path)
            logging.info(f"Successfully downloaded {dest_path.name} ({dest_path.stat().st_size / (1024*1024):.2f} MB)")
            return
        except Exception as e:
            logging.warning(f"Download attempt {attempt} failed: {e}")
            if temp_path.exists():
                temp_path.unlink()
            if attempt == max_retries:
                raise
            time.sleep(2 * attempt)


def build_rxnorm_concepts_table(conn: sqlite3.Connection) -> int:
    logging.info("Fetching RxNorm allconcepts from official NLM RxNav REST API...")
    headers = {"User-Agent": "Modawem-MedicationNormalizer/1.0", "Accept": "application/json"}
    req = Request(RXNORM_ALLCONCEPTS_URL, headers=headers)
    
    with urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    concept_group = data.get("minConceptGroup", {}).get("minConcept", [])
    logging.info(f"Retrieved {len(concept_group)} active RxNorm concepts.")

    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS rxnorm_concepts")
    cursor.execute("""
        CREATE TABLE rxnorm_concepts (
            rxcui TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            tty TEXT NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rxnorm_tty ON rxnorm_concepts(tty)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rxnorm_name ON rxnorm_concepts(name COLLATE NOCASE)")

    rows_to_insert = []
    for item in concept_group:
        rxcui = str(item.get("rxcui", "")).strip()
        name = str(item.get("name", "")).strip()
        tty = str(item.get("tty", "")).strip()
        if rxcui and name:
            rows_to_insert.append((rxcui, name, tty))

    cursor.executemany("INSERT OR REPLACE INTO rxnorm_concepts (rxcui, name, tty) VALUES (?, ?, ?)", rows_to_insert)
    conn.commit()

    # Also save CSV for quick inspection
    with open(RXNORM_CONCEPTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["rxcui", "name", "tty"])
        writer.writerows(rows_to_insert)

    logging.info(f"Saved {len(rows_to_insert)} RxNorm concepts to SQLite and {RXNORM_CONCEPTS_CSV.name}")
    return len(rows_to_insert)


def build_openfda_ndc_table(conn: sqlite3.Connection) -> int:
    zip_path = DATA_REF_DIR / "drug-ndc-0001-of-0001.json.zip"
    if not zip_path.exists() or zip_path.stat().st_size < 1000:
        download_with_progress(OPENFDA_NDC_URL, zip_path)

    logging.info(f"Extracting and parsing OpenFDA NDC JSON from {zip_path.name}...")
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS openfda_ndc")
    cursor.execute("""
        CREATE TABLE openfda_ndc (
            product_ndc TEXT PRIMARY KEY,
            generic_name TEXT,
            brand_name TEXT,
            active_ingredients TEXT,
            dosage_form TEXT,
            route TEXT,
            product_type TEXT,
            marketing_status TEXT,
            rxcui TEXT,
            pharm_class TEXT
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ndc_generic ON openfda_ndc(generic_name COLLATE NOCASE)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ndc_brand ON openfda_ndc(brand_name COLLATE NOCASE)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ndc_rxcui ON openfda_ndc(rxcui)")

    total_records = 0
    with zipfile.ZipFile(zip_path, "r") as z:
        namelist = z.namelist()
        json_filename = [n for n in namelist if n.endswith(".json")][0]
        logging.info(f"Streaming JSON file: {json_filename}")
        
        with z.open(json_filename) as f:
            # We can parse the JSON; in Python standard json, loading 300MB takes ~5s on modern CPUs
            data = json.load(f)
            results = data.get("results", [])
            total_records = len(results)
            logging.info(f"Loaded {total_records} drug products from OpenFDA NDC.")

            rows_to_insert = []
            for item in results:
                product_ndc = str(item.get("product_ndc", "")).strip()
                if not product_ndc:
                    product_ndc = str(item.get("product_id", "")).strip()
                if not product_ndc:
                    continue

                generic_name = item.get("generic_name") or ""
                brand_name = item.get("brand_name") or item.get("brand_name_base") or ""
                
                # Active ingredients format: list of dicts [{'name': '...', 'strength': '...'}]
                active_ing = item.get("active_ingredients") or []
                active_ing_str = json.dumps(active_ing, ensure_ascii=False) if active_ing else ""

                dosage_form = item.get("dosage_form") or ""
                route_list = item.get("route") or []
                route = "; ".join(route_list) if isinstance(route_list, list) else str(route_list)

                product_type = item.get("product_type") or ""
                marketing_status = item.get("marketing_status") or ""

                openfda = item.get("openfda") or {}
                rxcuis = openfda.get("rxcui") or []
                rxcui_str = "; ".join(rxcuis) if isinstance(rxcuis, list) else str(rxcuis)

                pharm_classes = openfda.get("pharm_class_cs") or openfda.get("pharm_class_epc") or []
                pharm_class_str = "; ".join(pharm_classes) if isinstance(pharm_classes, list) else str(pharm_classes)

                rows_to_insert.append((
                    product_ndc,
                    generic_name,
                    brand_name,
                    active_ing_str,
                    dosage_form,
                    route,
                    product_type,
                    marketing_status,
                    rxcui_str,
                    pharm_class_str,
                ))

            cursor.executemany("""
                INSERT OR REPLACE INTO openfda_ndc (
                    product_ndc, generic_name, brand_name, active_ingredients,
                    dosage_form, route, product_type, marketing_status, rxcui, pharm_class
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows_to_insert)
            conn.commit()

            # Export clean sample / summary CSV of 25,000 top records for rapid scanning
            with open(OPENFDA_NDC_CSV, "w", newline="", encoding="utf-8") as csv_f:
                writer = csv.writer(csv_f)
                writer.writerow([
                    "product_ndc", "generic_name", "brand_name", "active_ingredients",
                    "dosage_form", "route", "product_type", "marketing_status", "rxcui"
                ])
                for r in rows_to_insert[:25000]:
                    writer.writerow(r[:-1])

    logging.info(f"Inserted {total_records} OpenFDA NDC records into SQLite table 'openfda_ndc'.")
    return total_records


def main() -> None:
    start_time = time.time()
    logging.info(f"Official Google Drive Reference Dataset Location: {GOOGLE_DRIVE_DATASET_URL}")
    gdrive_db = Path(GOOGLE_DRIVE_DATASET_URL) / "drug_reference.sqlite" if Path(GOOGLE_DRIVE_DATASET_URL).exists() else None
    if not SQLITE_PATH.exists() and gdrive_db and gdrive_db.exists():
        logging.info(f"Restoring reference database from Google Drive local cache: {gdrive_db}")
        import shutil
        shutil.copy(gdrive_db, SQLITE_PATH)

    logging.info(f"Initializing Reference Dataset Builder in {DATA_REF_DIR}...")
    conn = sqlite3.connect(SQLITE_PATH)
    
    rxnorm_count = build_rxnorm_concepts_table(conn)
    ndc_count = build_openfda_ndc_table(conn)

    # Sanity checks and summary counts
    cur = conn.cursor()
    cur.execute("SELECT tty, count(*) FROM rxnorm_concepts GROUP BY tty ORDER BY count(*) DESC")
    tty_counts = cur.fetchall()
    logging.info(f"RxNorm Concept distribution by TTY: {tty_counts}")

    cur.execute("SELECT count(*) FROM openfda_ndc WHERE rxcui != ''")
    ndc_with_rxcui = cur.fetchone()[0]
    logging.info(f"OpenFDA records with linked RxCUI: {ndc_with_rxcui} / {ndc_count} ({ndc_with_rxcui / max(ndc_count, 1) * 100:.1f}%)")

    conn.close()
    elapsed = time.time() - start_time
    logging.info(f"Full-Scale Reference Dataset Build Complete in {elapsed:.1f}s.")
    logging.info(f"SQLite DB: {SQLITE_PATH} ({SQLITE_PATH.stat().st_size / (1024*1024):.1f} MB)")


if __name__ == "__main__":
    main()
