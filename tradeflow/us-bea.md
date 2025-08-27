# US Bureau of Economic Analysis (BEA) Integration Specification

## Overview

Create a comprehensive US-BEA data integration system that combines Exiobase MRIO data with US Bureau of Economic Analysis API data to generate relational trade flow tables. This system extends our existing exiobase/tradeflow architecture to include detailed US trade analysis with enhanced state-level and industry-specific insights. Developed by referencing [US generate_import_factors.py](https://github.com/USEPA/USEEIO/tree/master/import_emission_factors).

### Upcoming Reports
- State-to-state domestic trade flows
- State export competitiveness analysis
- Import dependency by state

## Configuration Settings

Get your [BEA API Key](https://apps.bea.gov/api/signup/)

**Year**: 2019 (from config.yaml)
**Country**: US (from config.yaml) 
**Trade Flows**: domestic, imports, exports (from config.yaml)
**Base Architecture**: Leverage existing exiobase/tradeflow preprocessing and Exiobase data downloads

**Usage**:
```bash
# Using BEA API key from webroot/.env file
python us-bea.py

# Using command line API key
python us-bea.py --bea-key YOUR_API_KEY

# Get help on available parameters
python us-bea.py --help
```

## Data Sources Integration

### 1. Exiobase Data (Primary)
- **Source**: Pre-downloaded IOT_[year]_pxp.zip (reuse existing download process if not available)
- **Components**: Z-matrix (inter-industry flows), Y-matrix (final demand), F-matrix (environmental extensions)
- **Processing**: Utilize existing trade.py preprocessing patterns for matrix manipulation
- **Output**: Core trade flows using established trade_id relational structure

### 2. BEA API Data (Enhancement)  
- **API Endpoint**: https://apps.bea.gov/api/data/
- **Key Datasets**: 
  - International Trade in Goods and Services (includes state-level export data)
  - Input-Output Tables (industry relationships)
  - Import/Export Price Indexes
- **Authentication**: Store you BEA API key in an .env file excluded by .gitignore

### 3. FEDEFL Integration
- **Source**: Federal LCA Commons Elementary Flow List
- **Purpose**: Generate flow.csv with comprehensive flow details for each Flow UUID
- **Fields**: FlowUUID, Flowable, Context, Unit, flow metadata

## Relational Database Design (CSV Tables)

### Core Trade Tables (Enhanced from existing)

#### trade.csv (Base Table)
trade_id, year, region1, region2, industry1, industry2, amount

- **trade_id**: 5-value composite key (year, region1, region2, industry1, industry2)
- Links to all other tables as primary foreign key

#### bea_trade_detail.csv (BEA API Enhancement)  
trade_id, bea_commodity_code, bea_industry_code, trade_balance, import_value, export_value, trade_partner_state, transport_mode

#### state_trade_flows.csv (State-Level Analysis)
trade_id, origin_state, destination_state, state_industry_code, flow_value, flow_type, employment_impact

#### trade_price_indices.csv (Economic Indicators)
trade_id, import_price_index, export_price_index, exchange_rate, price_year, currency_adjustment_factor

### Enhanced Factor Tables

#### flow.csv (FEDEFL Integration)
flow_uuid, flowable, context, unit, compartment, flow_class, preferred, external_reference

#### bea_industry_mapping.csv (Industry Concordance)
industry_id, exiobase_sector, bea_sector_code, bea_sector_name, naics_code, aggregation_level

#### trade_factor_bea.csv (BEA-Specific Factors) 
trade_id, factor_id, coefficient_value, bea_multiplier, regional_adjustment, data_source

### Analytical Enhancement Tables

#### export_competitiveness.csv (Export Analysis)
trade_id, revealed_comparative_advantage, export_sophistication_index, market_share, growth_rate

#### import_dependency.csv (Import Analysis)  
trade_id, import_penetration_ratio, supply_chain_vulnerability, alternative_suppliers, strategic_importance

#### state_industry_impacts.csv (State Economic Impact)
state_code, industry_code, direct_jobs, indirect_jobs, induced_jobs, total_output_impact, tax_revenue_impact

## Implementation Architecture

### Primary Module: us-bea.py

```python
class USBEATradeFlow(ExiobaseTradeFlow):
    """
    Extends ExiobaseTradeFlow with BEA API integration and enhanced analytics
    """
    
    def __init__(self):
        super().__init__()
        self.bea_api_key = self.load_bea_credentials()
        self.fedefl_flows = self.load_fedefl_data()
    
    def process_all_tradeflows(self):
        """Main processing pipeline for all three tradeflows"""
        for tradeflow in ['domestic', 'imports', 'exports']:
            self.process_bea_enhanced_tradeflow(tradeflow)
    
    def process_bea_enhanced_tradeflow(self, tradeflow):
        """Enhanced processing with BEA API integration"""
        # 1. Generate base trade data using existing Exiobase patterns
        # 2. Enhance with BEA API data
        # 3. Create state-level disaggregation  
        # 4. Generate relational output tables
        # 5. Create flow.csv from FEDEFL
```

### Supporting Modules

#### us-bea_api_client.py
- BEA API authentication and data retrieval
- Rate limiting and error handling
- Data caching and preprocessing

#### us-state_trade_analyzer.py  
- State-level trade flow disaggregation
- Economic impact calculations
- Employment and output multipliers

#### us-fedefl_integration.py
- FEDEFL flow data integration  
- UUID mapping and flow metadata
- Environmental flow standardization

## Processing Pipeline

### Phase 1: Base Data Generation
1. **Exiobase Processing** (leverage existing trade.py patterns)
   - Download IOT_[year]_pxp.zip if not available
   - Extract Z, Y, F matrices 
   - Generate base trade.csv with trade_id structure
   - Create industry.csv and factor.csv reference files

### Phase 2: BEA API Enhancement
2. **BEA Data Retrieval**
   - Fetch trade data by commodity and partner country
   - Retrieve state-level export statistics  
   - Pull industry input-output relationships
   - Download price indices and economic indicators

### Phase 3: Integration and Analytics  
3. **Data Integration**
   - Map Exiobase sectors to BEA industry codes
   - Reconcile trade values between data sources
   - Create comprehensive industry concordance
   - Generate enhanced trade factor coefficients

### Phase 4: State-Level Disaggregation
4. **State Analysis**
   - Disaggregate national flows to state level using BEA data
   - Calculate state-specific employment impacts
   - Analyze export competitiveness by state and industry
   - Create import dependency assessments

### Phase 5: Relational Output Generation
5. **CSV Table Creation**
   - Generate all relational tables using trade_id links
   - Create FEDEFL-based flow.csv
   - Output comprehensive state and industry impact tables
   - Ensure data consistency across all tables

## Output Structure Enhancement

```
year/[year]/
├── US/
│   ├── domestic/
│   │   ├── trade.csv                    # Base trade flows
│   │   ├── bea_trade_detail.csv        # BEA-enhanced trade details
│   │   ├── state_trade_flows.csv       # State-level flows  
│   │   ├── trade_factor_bea.csv        # BEA-specific coefficients
│   │   └── state_industry_impacts.csv  # State economic impacts
│   ├── imports/
│   │   ├── trade.csv
│   │   ├── bea_trade_detail.csv
│   │   ├── import_dependency.csv       # Import analysis
│   │   ├── trade_price_indices.csv     # Economic indicators
│   │   └── trade_factor_bea.csv
│   └── exports/
│       ├── trade.csv  
│       ├── bea_trade_detail.csv
│       ├── export_competitiveness.csv  # Export analysis
│       ├── state_trade_flows.csv
│       └── trade_factor_bea.csv
├── industry.csv                         # Enhanced industry mapping
├── factor.csv                           # Base environmental factors
├── flow.csv                            # FEDEFL flow details
├── bea_industry_mapping.csv            # Industry concordance
└── reference/
    ├── state_codes.csv                 # State reference data
    ├── naics_mapping.csv              # NAICS concordance  
    └── bea_sectors.csv                # BEA sector definitions
```

## Key Innovations

### 1. Enhanced Relational Structure
- All tables link via trade_id for comprehensive analysis
- State-level disaggregation maintains trade_id relationships
- Multiple data sources integrated through common identifiers

### 2. Comprehensive Coverage  
- **Domestic**: Intra-US state-to-state trade flows with employment impacts
- **Imports**: Dependency analysis, alternative supplier assessment, price impacts
- **Exports**: Competitiveness analysis, state export specializations, market opportunities

### 3. Policy-Relevant Analytics
- Trade balance implications by state and industry
- Supply chain vulnerability assessments  
- Economic impact multipliers for policy analysis
- Export competitiveness and market share analysis

## Data Quality and Validation

### 1. Cross-Source Reconciliation
- Compare Exiobase and BEA trade values for consistency
- Flag significant discrepancies for manual review
- Apply scaling factors where appropriate

### 2. State-Level Validation
- Ensure state exports sum to national totals
- Validate employment multipliers against BEA benchmarks
- Cross-check industry classifications

### 3. FEDEFL Integration Quality
- Verify Flow UUID mapping completeness
- Ensure environmental flow consistency
- Validate units and contexts

## Performance Considerations

### 1. API Rate Limiting
- Implement intelligent caching for BEA API calls
- Batch requests efficiently to minimize API calls
- Store intermediate results for debugging and reprocessing

### 2. Memory Management  
- Process large datasets in chunks (following existing patterns)
- Use efficient pandas operations for matrix manipulations
- Implement garbage collection for large temporary objects

### 3. Scalability
- Design for easy extension to other years
- Enable selective processing of specific tradeflows
- Support incremental updates and data refreshes

This specification creates a comprehensive framework that leverages existing Exiobase processing capabilities while adding substantial BEA API integration and state-level analytical capabilities. The relational design ensures data consistency and enables complex multi-dimensional analysis of US trade flows.