#!/usr/bin/env python3
"""
Trade-only EXIOBASE extraction (PyCharm/Jupyter friendly)

- Builds EXIO path as: <exio_base>/IOT_<year>_pxp
- Reads/creates industry.csv (sector name -> industry_id)
- Writes one trade file per country: trade_<CC>.csv
- If a sector doesn't map, sets industry to '-1'
"""

from pathlib import Path
from datetime import datetime
import argparse
import warnings
import os
import re
import pandas as pd
import pymrio
from pandas.errors import EmptyDataError

warnings.filterwarnings("ignore", category=FutureWarning)

# ====== DEFAULTS (can be overridden by CLI) ======
DEFAULT_EXIO_BASE  = r"H:\Exiobase Unzipped"
DEFAULT_OUTPUT_DIR = r"H:\Exiobase Unzipped\Output"
DEFAULT_INDUSTRY_CSV = r"H:\Industry\industry.csv"

DEFAULT_YEAR    = 2019
DEFAULT_COUNTRIES = "US"          # comma-separated list: "US" or "US,UK,DE"
DEFAULT_FLOW   = "imports"        # imports | exports | domestic

# ---------- path helpers ----------
def build_exio_path(exio_base: str, year: int) -> Path:
    # Unzipped EXIOBASE directory layout: IOT_<year>_pxp
    return Path(exio_base) / f"IOT_{year}_pxp"

def ensure_paths(exio_path: Path, output_dir: Path) -> bool:
    output_dir.mkdir(parents=True, exist_ok=True)
    if not exio_path.exists():
        print(f"[ERROR] EXIOBASE path not found: {exio_path}")
        return False
    return True

def parse_exiobase_model(exio_path: Path):
    print(f"Parsing EXIOBASE at: {exio_path}")
    try:
        return pymrio.parse_exiobase3(str(exio_path))
    except Exception as e:
        print(f"[ERROR] Failed to parse EXIOBASE at {exio_path}:\n{e}")
        return None

# ---------- industry.csv creation / loading ----------
def _normalize_to_code5(name: str) -> str:
    cleaned = re.sub(r'[^A-Za-z0-9]', '', str(name)).upper() or "SECTR"
    return (cleaned + "XXXXX")[:5]

def _dedupe_codes(codes):
    seen = {}
    pool = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    out = []
    for c in codes:
        if c not in seen:
            seen[c] = 0
            out.append(c)
        else:
            seen[c] += 1
            idx = seen[c] % len(pool)
            out.append(c[:4] + pool[idx])
    return out

def _build_mapping_from_model(exio_model) -> pd.DataFrame:
    Z = exio_model.Z
    Z.index.names = ["from_region", "from_sector"]
    Z.columns.names = ["to_region", "to_sector"]
    from_names = pd.Index(Z.index.get_level_values("from_sector")).unique()
    to_names   = pd.Index(Z.columns.get_level_values("to_sector")).unique()
    sector_names = pd.Index(from_names).union(to_names)
    tentative = [_normalize_to_code5(n) for n in sector_names]
    unique_codes = _dedupe_codes(tentative)
    return pd.DataFrame({"name": sector_names, "industry_id": unique_codes}).sort_values("name")

def create_or_fix_industry_csv(exio_model, industry_csv: Path):
    need = (not industry_csv.exists()) or os.path.getsize(industry_csv) == 0
    if not need:
        # validate columns quickly
        try:
            df = pd.read_csv(industry_csv, nrows=5)
            if not {"name", "industry_id"}.issubset(df.columns):
                need = True
        except Exception:
            need = True
    if not need:
        print(f"industry.csv found at {industry_csv}")
        return
    print(f"Creating industry.csv at {industry_csv} ...")
    df = _build_mapping_from_model(exio_model)
    industry_csv.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_csv(industry_csv, index=False)
        print(f"Created industry.csv with {len(df)} rows.")
    except Exception as e:
        print(f"[WARN] Could not write industry.csv ({e}). Proceeding with in-memory mapping only.")

def load_sector_mapping(exio_model, industry_csv: Path) -> dict:
    def _read():
        try:
            return pd.read_csv(industry_csv)
        except EmptyDataError:
            return None
        except Exception:
            return None
    if (not industry_csv.exists()) or os.path.getsize(industry_csv) == 0:
        create_or_fix_industry_csv(exio_model, industry_csv)
    df = _read()
    if df is None or df.empty or not {"name","industry_id"}.issubset(df.columns):
        create_or_fix_industry_csv(exio_model, industry_csv)
        df = _read()
    if df is None or df.empty or not {"name","industry_id"}.issubset(df.columns):
        print("[WARN] Using in-memory sector mapping (file not usable).")
        df = _build_mapping_from_model(exio_model)
    return dict(zip(df["name"], df["industry_id"]))

# ---------- trade extraction ----------
def filter_by_tradeflow(z_long: pd.DataFrame, flow: str, country: str) -> pd.DataFrame:
    if flow == "imports":
        df = z_long[(z_long["to_region"] == country) & (z_long["from_region"] != country)].copy()
        thr = 0.01
    elif flow == "exports":
        df = z_long[(z_long["from_region"] == country) & (z_long["to_region"] != country)].copy()
        thr = 0.01
    elif flow == "domestic":
        df = z_long[(z_long["from_region"] == country) & (z_long["to_region"] == country)].copy()
        thr = 0.001
    else:
        print(f"[ERROR] Invalid flow: {flow}")
        return pd.DataFrame()
    before = len(df)
    df = df[df["flow"] > thr]
    print(f"{country} {flow}: threshold >{thr} -> kept {len(df)} / {before}")
    return df

def extract_trade_df(exio_model, flow: str, country: str, year: int, sector_map: dict) -> pd.DataFrame:
    Z = exio_model.Z.copy()
    Z.index.names = ["from_region", "from_sector"]
    Z.columns.names = ["to_region", "to_sector"]

    z_long = Z.stack(level=["to_region", "to_sector"]).reset_index()
    z_long.columns = ["from_region", "from_sector", "to_region", "to_sector", "flow"]

    z_filt = filter_by_tradeflow(z_long, flow, country)
    if z_filt.empty:
        return pd.DataFrame(columns=["trade_id","year","region1","region2","industry1","industry2","amount"])

    z_filt["industry1"] = z_filt["from_sector"].map(sector_map).fillna("-1")
    z_filt["industry2"] = z_filt["to_sector"].map(sector_map).fillna("-1")

    trade = (
        z_filt.groupby(["from_region", "to_region", "industry1", "industry2"])["flow"]
        .sum()
        .reset_index()
        .rename(columns={"from_region": "region1", "to_region": "region2", "flow": "amount"})
    )

    trade["year"] = year
    trade = trade.sort_values("amount", ascending=False).reset_index(drop=True)
    trade["trade_id"] = trade.index + 1
    return trade[["trade_id", "year", "region1", "region2", "industry1", "industry2", "amount"]]

# ---------- main ----------
def main(argv=None):
    parser = argparse.ArgumentParser(description="Trade-only EXIOBASE extractor")
    parser.add_argument("--exio_base", type=str, default=DEFAULT_EXIO_BASE,
                        help="Base folder containing unzipped EXIOBASE dirs (e.g., H:\\Exiobase Unzipped)")
    parser.add_argument("--output_dir", type=str, default=DEFAULT_OUTPUT_DIR,
                        help="Folder to write trade_<CC>.csv")
    parser.add_argument("--industry_csv", type=str, default=DEFAULT_INDUSTRY_CSV,
                        help="Path to industries.csv (name,industry_id)")
    parser.add_argument("--year", type=int, default=DEFAULT_YEAR,
                        help="EXIOBASE year (folder built as IOT_<year>_pxp)")
    parser.add_argument("--countries", type=str, default=DEFAULT_COUNTRIES,
                        help="Comma-separated list of EXIOBASE region codes, e.g. 'US' or 'US,UK,DE'")
    parser.add_argument("--flow", type=str, default=DEFAULT_FLOW, choices=["imports","exports","domestic"],
                        help="Which direction of flows to keep")

    args, unknown = parser.parse_known_args(argv)
    if unknown:
        print("Ignoring unknown args:", unknown)

    exio_path = build_exio_path(args.exio_base, args.year)
    output_dir = Path(args.output_dir)
    industry_csv = Path(args.industry_csv)

    print("=== Run settings ===")
    print(f"exio_base   : {args.exio_base}")
    print(f"year        : {args.year}")
    print(f"EXIO_PATH   : {exio_path}")
    print(f"output_dir  : {output_dir}")
    print(f"industry_csv: {industry_csv}")
    print(f"countries   : {args.countries}")
    print(f"flow        : {args.flow}")
    print("====================")

    if not ensure_paths(exio_path, output_dir):
        return

    start = datetime.now()
    exio = parse_exiobase_model(exio_path)
    if exio is None:
        return

    # Ensure/Load sector mapping
    create_or_fix_industry_csv(exio, industry_csv)
    sector_map = load_sector_mapping(exio, industry_csv)
    if not sector_map:
        print("[ERROR] No sector mapping available; aborting.")
        return

    # Process each requested country
    countries = [c.strip() for c in args.countries.split(",") if c.strip()]
    for c in countries:
        print(f"\n--- Building trade for country: {c} ---")
        trade_df = extract_trade_df(exio, args.flow, c, args.year, sector_map)
        out_csv = output_dir / f"trade_{c}.csv"
        trade_df.to_csv(out_csv, index=False, float_format="%.2f")
        print(f"Wrote {len(trade_df)} rows -> {out_csv}")

    print(f"\nDone in {(datetime.now() - start).total_seconds():.1f}s")


if __name__ == "__main__":
    main()
