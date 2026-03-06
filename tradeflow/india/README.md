# India State-Level Trade Flow Allocation

Allocates national India trade flow and economic data down to the state/UT level, producing matrices that integrate with the Exiobase MRIO pipeline.

## india-state-allocation.py

### What it processes

Reads national-level Indian economic data and disaggregates it across 36 states and union territories using sector output shares derived from GSDP and GSVA. The five allocation steps are:

1. **State × Sector output matrix** — GSDP scaled by GSVA sector shares per state
2. **State × Product export matrix** — national TradeStat exports allocated to states via sector output proxies; HS codes mapped to Exiobase products
3. **State × Product import matrix** — national TradeStat imports allocated to states via GSDP proportions; HS codes mapped to Exiobase products
4. **State A-matrices** — national Supply Use Table (SUT) technical coefficients scaled per state; used in-memory only, not written to disk
5. **india_states.csv** — state-level summary of total output, employment (placeholder), and population (placeholder)

### Uses config.yaml

Yes — reads `../config.yaml` (one level up, in `exiobase/tradeflow/`) via `config_loader.py` for the processing year (`YEAR`) and reference file paths (`industry.csv`). The year can be overridden with `--year`.

### Input data

All source files are expected in `exiobase/India_data/` (two levels up from this folder). The script scans that directory on startup and categorizes files automatically:

| Category | Matched by filename | Format |
|---|---|---|
| GSDP | contains `gsdp`, `sdp`, or `gdp` + `state` | CSV or Excel |
| GSVA / NSVA | contains `gsva`, `nsva`, or `value_added` | CSV or Excel |
| SUT / IOT | contains `sut`, `iot`, `input_output`, `supply_use`, or `revision` | CSV or Excel |
| Exports | contains `export` + `tradestat` | CSV or Excel |
| Imports | contains `import` + `tradestat` | CSV or Excel |
| State files | contains a state name (e.g. `gujarat`, `kerala`) | Excel |
| HS mapping | `HS_EXIOBASE_mapping.csv` (auto-generated if absent) | CSV |

State files (individual Excel files per state) are used as a fallback when consolidated GSDP or GSVA files are not present.

### Output

Sent to `webroot/trade-data/year/2023/IN/domestic/` by default. Override with `--output-dir`.

| File | Description |
|---|---|
| `state_sector_output.csv` | State × sector output matrix; columns: `state, sector, output, value_added, allocation_method` |
| `state_product_export.csv` | State × product export matrix; columns: `state, exiobase_product, export_value, hs_code, allocation_method` |
| `state_product_import.csv` | State × product import matrix; columns: `state, exiobase_product, import_value, hs_code, allocation_method` |
| `india_states.csv` | State summary; columns: `State, Output, Employment, Population` |
| `allocation_report.md` | Processing summary with row counts and totals per matrix |
| `HS_EXIOBASE_mapping.csv` | Saved to `India_data/` on first run if not already present |

### Run

```bash
# Run from exiobase/tradeflow/
python india/india-state-allocation.py

# Specify a different data directory
python india/india-state-allocation.py --data-dir ../India_data

# Specify a year (overrides config.yaml)
python india/india-state-allocation.py --year 2019

# Specify a custom output directory
python india/india-state-allocation.py --output-dir ../../trade-data/year/2019/IN/domestic
```

### Dependencies

```bash
pip install pandas numpy openpyxl
```

`openpyxl` is required for reading Excel (`.xlsx`/`.xls`) source files. The script will warn and continue with limited functionality if it is not installed.
