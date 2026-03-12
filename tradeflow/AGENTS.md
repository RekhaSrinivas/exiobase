# Annual trade data processing

The following provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an Exiobase data processing project that extracts and transforms multiregional input-output (MRIO) data for economic and environmental analysis. The project processes trade flows, industry factors, and environmental impacts from the Industry Database.

## Architecture

### Core Components

- **config.yaml**: Central configuration for countries, trade flows, processing parameters
- **config_loader.py**: Smart configuration handling with domestic/non-domestic file selection
- **main.py**: Automated batch processing with progress tracking

### Data Flow Architecture

1. **Data Source**: Exiobase v3 database files (parsed using pymrio library)
2. **Core Matrices**:
   - **Z matrix**: Inter-industry flows between regions/sectors
   - **Y matrix**: Final demand  
   - **F matrix**: Environmental extension factors
3. **Processing**: Transform matrices into relational format for database storage
4. **Output**: Structured CSV files with comprehensive environmental impact data

## Development Environment

### Python Environment Setup
```bash
# Create and activate virtual environment
python -m venv env
source env/bin/activate  # macOS/Linux

env\Scripts\activate.bat # PC

# Install required dependencies - Not needed if you run from Claude Code CLI.
pip install pandas numpy pymrio sqlalchemy psycopg2-binary requests pyyaml
```


#### Automated Batch Processing:
```bash
# Process multiple countries automatically
python main.py

# Update current country manually
python update_current_country.py CN
```

## Processing Pipeline (CSV Generation Order)

The scripts are run in this specific order to ensure proper data dependencies:

main.py will first download the Exiobase year file. Takes about 10 minutes for a 535 MB file.

### 1. **trade.py** - Primary Data Extraction and Processing
- **Input**: Exiobase Z-matrix (inter-industry flows) and F-matrices (environmental extensions)
- **Output**: 
  - `trade.csv` - Core trade flows (trade_id, year, region1, region2, industry1, industry2, amount)
  - `industry.csv` - Industry sector mapping with 5-character codes
  - `factor.csv` - Environmental factor definitions (721 factors)
  - `trade_factor.csv` - Environmental coefficients (120 selected factors for imports/exports)
  - `trade_factor_lg.csv` - All environmental coefficients (721 factors for domestic flows)
- **Purpose**: Primary script that extracts trade flows and creates environmental impact coefficients
- **Key Features**: 
  - Handles imports, exports, and domestic flows based on config
  - Creates both small (120 factors) and large (721 factors) coefficient files
  - For domestic flows, extracts intra-country flows (country→same country)
- **Processing time**: \~2-3 minutes per country

### 2. **trade_impact.py** - Aggregated Environmental Impacts
- **Input**: `trade.csv` + `trade_factor_lg.csv` (domestic) or `trade_factor.csv` (others)
- **Output**: `trade_impact.csv`
- **Purpose**: Comprehensive environmental impact summary per trade transaction
- **Processing time**: \~10-15 seconds per country

### 3. **trade_resource.py** - Specialized Resource Analysis
- **Input**: `trade_factor_lg.csv` or `trade_factor.csv`
- **Output**: 
  - `trade_employment.csv` - Employment impact analysis
  - `trade_resource.csv` - Resource use analysis (water, energy, land)
  - `trade_material.csv` - Material flow analysis
- **Purpose**: Creates three specialized output files optimized for size and processing performance
- **Processing time**: \~5-15 seconds per country


### Running Scripts

#### Individual Script Execution:

Run main.py to invove the following:

```bash
# Create a virtual environment (commands above)
# Run to invoke all 3 scripts
python main.py

# Or run scripts in order
python trade.py # Creates trade.csv, trade_factor.csv, industry.csv, factor.csv
python trade_impact.py
python trade_resource.py
```

## Configuration Management

### Country List Handling
- **Explicit list**: `COUNTRY: {list: "CN,DE,JP", current: "CN"}`
- **All countries**: `COUNTRY: {list: "all"}` - Auto-discovers existing country folders
- **Default set**: `COUNTRY: {list: "default"}` - Uses predefined 12-country set
- **Auto-population**: Missing `current` field automatically populated during processing
- **Auto-cleanup**: `current` field automatically removed when batch processing completes

### Trade Flow Types
- **imports**: Flows TO the country (from other countries)
- **exports**: Flows FROM the country (to other countries)  
- **domestic**: Flows WITHIN the country (intra-country only)

### File Selection Logic
- **Domestic flows**: Automatically uses `trade_factor_lg.csv` (all 721 factors) if available
- **Import/Export flows**: Uses `trade_factor.csv` (120 selected factors) for performance
- **Smart fallback**: If `_lg` version doesn't exist, falls back to standard version

## Data Processing Patterns

### Exiobase Data Structure
- **Regions**: 44 countries + 5 rest-of-world regions (AT, BE, CN, US, etc.)
- **Industries**: 163 detailed sectors aggregated to \~200 standardized codes
- **Extensions**: Air emissions, employment, energy, land use, materials, water, etc.

### Trade Factors Strategy: Two-File System

The project uses a dual-file approach to balance comprehensive environmental coverage with processing performance:

#### **trade_factor.csv** (Small File - 120 Selected Factors)
- **Used for**: Imports and Exports (international trade flows)
- **Size**: ~50MB, manageable for all processing scripts
- **Factor Selection**: Prioritized environmental impacts (CO2, CH4, N2O, employment, energy, water, etc.)
- **Rationale**: International trade volumes are massive - using all 721 factors would create files >1.5GB
- **Performance**: Fast processing, no memory issues
- **Coverage**: Captures key environmental impacts while maintaining system performance

#### **trade_factor_lg.csv** (Large File - All 721 Factors) 
- **Used for**: Domestic flows (intra-country trade only)
- **Size**: ~1.5GB when created with `-lag` flag in trade.py
- **Factor Coverage**: Complete environmental analysis (all extensions: air, water, land, materials, employment, energy)
- **Rationale**: Domestic trade volumes are smaller, so comprehensive analysis is feasible
- **Warning**: May cause Node.js memory errors in trade_resource.py processing
- **Usage**: Only recommended for thorough domestic environmental analysis

#### **Smart File Selection Logic**
- **config_loader.py** automatically selects the appropriate file:
  - **Domestic flows**: Uses `trade_factor_lg.csv` if available, falls back to `trade_factor.csv`
  - **International flows**: Always uses `trade_factor.csv` for performance
- **Processing scripts** (trade_impact.py, trade_resource.py) detect which file to use based on tradeflow type

## File Path Conventions

- **Exiobase data**: `exiobase_data/IOT_{year}_pxp.zip`
- **Country outputs**: `year/{year}/{country}/{tradeflow}/`
- **Reference files**: `year/{year}/industry.csv`, `year/{year}/factor.csv`
- **Run documentation**: `runnote.md` (overwritten after each full run)

## Progress Tracking System

### Run Notes
- **runnote-inprogress.md**: Created during processing, tracks progress and timing
- **runnote.md**: Final summary created after successful completion, overwrites previous
- **Auto-cleanup**: Progress file deleted after creating final summary

### Key Information Tracked
- Trade factors file used (`trade_factor.csv` vs `trade_factor_lg.csv`)
- Processing timestamps and duration
- File generation summary
- Environmental impact coverage details

## Output Files Structure

### Core Trade Data
- **trade.csv**: `trade_id, year, region1, region2, industry1, industry2, amount`

### Environmental Impact Data  
- **trade_factor.csv**: Selected factors for imports/exports (120 factors)
- **trade_factor_lg.csv**: All factors for domestic flows (721 factors)
- **trade_impact.csv**: Comprehensive impact summary per trade transaction
- **trade_employment.csv**: Employment impact analysis
- **trade_resource.csv**: Resource use analysis (water, energy, land)
- **trade_material.csv**: Material flow analysis

### Reference Files
- **industry.csv**: Sector mapping with standardized 5-character codes
- **factor.csv**: Environmental factor definitions with units and contexts

## Key Libraries

- **pymrio**: Primary library for parsing Exiobase data files
- **pandas**: Data manipulation and transformation
- **numpy**: Numerical computations and coefficient generation
- **pathlib**: Modern file path handling
- **yaml**: Configuration file management

## Performance Optimizations

- **Domestic flows**: All 721 factors (comprehensive analysis feasible)
- **International flows**: 120 selected factors (performance-optimized)
- **Smart file selection**: Automatic `_lg` vs standard file detection
- **Batch processing**: Multi-level timeout protection with automatic progression
- **Memory management**: Chunked processing for large datasets
- **Resume functionality**: Automatically skips already completed countries

## Timeout Configuration

The system implements a three-tier timeout hierarchy for robust processing management in **main.py** (batch processor):

1. **Script timeout**: 20 minutes (1200 seconds) per individual script
   - Prevents any single script from hanging indefinitely
   - Applies to each of the 3 processing scripts per country: `trade.py`, `trade_impact.py`, `trade_resource.py`
   - Most granular level of timeout protection
   - Implementation: `timeout=1200` in subprocess.run() calls

2. **Country timeout**: 60 minutes (3600 seconds) per country total
   - Limits total processing time for all scripts in a single country
   - Provides real-time countdown: "Country time remaining: X.X minutes"
   - Prevents any country from consuming excessive batch time
   - Implementation: `country_timeout = 3600` in main.py

3. **Batch timeout**: 5 hours (18000 seconds) for entire batch
   - Overall time limit for processing all countries in the list
   - Shows remaining batch time: "Batch time remaining: X.X hours"
   - Most restrictive timeout - will stop processing when reached
   - Implementation: `batch_timeout = 18000` in main.py

**Timeout Priority**: The most restrictive timeout wins. If any timeout is exceeded, processing stops gracefully with clear status reporting and automatic resume capability.

## Best Practices

1. **Always run scripts in the specified order** (dependencies matter)
2. **Use batch processing** for multiple countries (main.py)
3. **Check runnote.md** for processing details and file usage
4. **Domestic flows**: Expect longer processing times but comprehensive coverage
5. **International flows**: Optimized for performance with key environmental impacts

## Troubleshooting

### Common Processing Failures

#### **Memory Errors (Critical Issue)**
- **Symptom**: `"FATAL ERROR: v8::ToLocalChecked Empty MaybeLocal"` after ~10 minutes
- **Cause**: `trade_factor_lg.csv` files (~1.5GB) exceed Node.js memory limits
- **Solution**: Use default `python trade.py` (not `python trade.py -lag`)
- **Prevention**: Avoid large factor files for international trade processing

#### **Missing Files**
- **Symptom**: `"⚠️ WARNING: trade_factor.csv not found"`
- **Solution**: Run scripts in correct dependency order: `trade.py` → `trade_impact.py` → `trade_resource.py`
- **Check**: Verify previous script completed successfully without errors

#### **Empty Domestic Flows**
- **Symptom**: No trade flows found for domestic processing
- **Solution**: Check country codes match Exiobase regions exactly (CN, DE, JP, US, etc.)
- **Diagnostic**: Look for flow count messages in script output (>0, >0.001, >0.01)

#### **Timeout Errors**
- **Script timeout**: 20 minutes per individual script
- **Country timeout**: 60 minutes per country total  
- **Batch timeout**: 5 hours for entire batch processing
- **Solution**: Processing automatically resumes and skips completed countries

#### **Performance Issues**
- **International flows**: Use optimized 120-factor selection for performance
- **Domestic flows**: Expect longer processing times with comprehensive 721-factor coverage
- **Chunked processing**: Large datasets processed in 10,000-row chunks to manage memory

#### **Configuration Errors**
- **Country structure**: Verify COUNTRY dict format with proper 'current' field population
- **Auto-resolution**: System handles "all", "default", or explicit country lists automatically
- **File paths**: Ensure base directory structure exists before processing

### Error Recovery Mechanisms

- **Automatic fallbacks**: Scripts use simulated data when Exiobase downloads fail
- **Resume functionality**: Batch processing skips countries with existing `runnote.md`
- **Smart file selection**: Automatically chooses appropriate factor file based on trade flow type
- **Progress tracking**: `runnote-inprogress.md` tracks processing stages for debugging