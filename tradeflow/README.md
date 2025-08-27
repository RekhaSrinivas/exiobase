# Primary tables: <span style="color:#aaa">trade, factor, industry</span>

Table naming designed for 3rd graders. [View Report Sample](../../profile/footprint/sample.html) from [Exiobase .csv output](https://github.com/ModelEarth/trade-data/tree/main/year) and [US State Data](../../trade/footprint/)

**The trade_id field** in trade.csv relates 5 values (year, region1, region2, industry1, industry2) to multiple impact factors for each trade row.

**The factor_id field** represents 721 unique impacts applied to each annual trade row (for imports, exports and domestic).

Trade is traditionally called flow, but the term lacks clarity when relating annual trade rows to multiple factors.

Later, the 6-character "commodity" sectors can reside in the 5-character "trade" tables, or in tables starting with "commodity".

Combing state-to-state consumption: [Exiobase plus BEA](bea)

## Processing Command

To generate CSV file output configured in config.yaml, run the automated batch processing for [our related project](https://github.com/ModelEarth/projects/issues/30):

```bash
python main.py
```

## Processing Times

| config.yaml | trade.py | trade_impact.py | trade_resource.py |
|--------------|----------|----------------|-------------------|
| **2019/US/exports** | **2m 14s**<br>**188,735 trade flows**<br/>125,148 trade factors | **5.3s**<br>**188,735 trade impacts** | **9.0s**<br>**38,935 total rows**<br/>(3,469 employment<br/>28,844 resources<br/>6,622 materials) |
| **2019/US/imports** | **2m 11s**<br>**126,166 trade flows**<br/>19,425 trade factors | **3.5s**<br>**126,166 trade impacts** | **5.6s**<br>**7,850 total rows**<br/>(2,578 employment<br/>3,926 resources<br/>1,346 materials) |
| **2019/US/domestic** | **2m 18s**<br>**21,518 trade flows**<br/>11,832 trade factors | **1.7s**<br>**21,518 trade impacts** | **1.9s**<br>**4,272 total rows**<br/>(421 employment<br/>2,656 resources<br/>1,195 materials) |

- trade.py: Includes Exiobase download, trade flow extraction, and trade_factor.csv generation
- trade_impact.py: Creates aggregated environmental impact summary (22 columns)
- trade_resource.py: Creates 3 specialized files (employment, resource, material analysis)
- Total processing time: ~2m 30s for 188,735 trade flows
- Well within timeout limits (20 min/script, 60 min/country, 5 hours/batch)

The main.py command generates the following CSV files for each country/tradeflow combination:
- `factor.csv` - Environmental factor definitions (721 factors)
- `industry.csv` - Industry sector mapping  
- `trade.csv` - Core trade flows (trade_id, year, region1, region2, industry1, industry2, amount)
- `trade_factor.csv` - Environmental coefficients (120 selected factors for imports/exports)
- `trade_factor_lg.csv` - All environmental coefficients (721 factors for domestic flows)
- `trade_impact.csv` - Aggregated environmental impacts
- `trade_resource.csv` - Resource use analysis
- `trade_material.csv` - Material flow analysis  
- `trade_employment.csv` - Employment impact analysis

