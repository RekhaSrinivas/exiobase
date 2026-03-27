#!/usr/bin/env python3
"""
US Bureau of Economic Analysis (BEA) Enhanced Trade Flow Analysis - OPTIMIZED

Extends ExiobaseTradeFlow with BEA API integration for comprehensive US trade analysis.
Now includes file existence checking to avoid regenerating existing trade.csv files.

Usage:
    python bea/main.py --bea-key YOUR_API_KEY
    python bea/main.py  # Uses BEA_API_KEY from webroot .env file
    python bea/main.py --force-regen  # Force regeneration even if files exist

Optimization: Checks for existing trade.csv files before regenerating them.
"""

import sys
import pandas as pd
import numpy as np
import time
import argparse
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Allow imports from parent tradeflow directory (config_loader, trade, etc.)
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import existing modules
from config_loader import load_config, get_file_path, get_reference_file_path

# Import US-BEA specialized modules
from main_api_client import BEAAPIClient
from main_trade_analyzer import StateTradeAnalyzer
from main_fedefl_integration import FEDEFLIntegrator

class USBEATradeFlow:
    def __init__(self, bea_api_key=None, force_regeneration=False):
        # Load configuration
        self.config = load_config()
        
        # Load BEA API key from multiple sources
        self.bea_api_key = self._load_bea_api_key(bea_api_key)
        
        # Optimization settings
        self.force_regeneration = force_regeneration
        
        # Initialize validation tracking
        self.validation_issues = []
        self.processing_log = []
        
        # Initialize US-BEA specialized components
        self.bea_client = BEAAPIClient(self.bea_api_key)
        self.state_analyzer = StateTradeAnalyzer(self.config)
        self.fedefl_integrator = FEDEFLIntegrator()
        
        print(f"US-BEA Trade Flow Analysis for {self.config['YEAR']} {self.config['COUNTRY']}")
        print(f"Trade flows: {self.config['TRADEFLOW']}")
        if force_regeneration:
            print("Force regeneration: Enabled - will recreate all trade.csv files")
        else:
            print("Optimization: Will skip existing trade.csv files")
        
    def _load_bea_api_key(self, provided_key):
        """Load BEA API key from command line, .env files, or environment.
        Returns None if not found — BEA API calls will fall back to empty DataFrames."""
        if provided_key:
            return provided_key

        # Search .env files in priority order
        search_paths = [
            Path(__file__).parents[2] / 'docker' / '.env',   # webroot/docker/.env
            Path(__file__).parents[2] / '.env',               # webroot/.env
        ]
        for env_path in search_paths:
            if env_path.exists():
                load_dotenv(env_path)
                env_key = os.getenv('BEA_API_KEY')
                if env_key:
                    print(f"Loaded BEA API key from {env_path}")
                    return env_key

        # Try system environment
        env_key = os.getenv('BEA_API_KEY')
        if env_key:
            print("Loaded BEA API key from system environment")
            return env_key

        print("BEA API key not found — BEA API enhancement will be skipped.")
        print("To enable: add BEA_API_KEY=your_key to webroot/docker/.env or webroot/.env")
        print("Register at https://apps.bea.gov/api/signup/")
        return None
    
    def process_all_tradeflows(self):
        """Main processing pipeline for enhanced BEA trade analysis"""
        start_time = time.time()
        
        tradeflows = self.config['TRADEFLOW']
        if isinstance(tradeflows, str):
            if tradeflows.lower() == 'all':
                tradeflows = ['imports', 'exports', 'domestic']
            else:
                tradeflows = [t.strip() for t in tradeflows.split(',')]
            
        print(f"\nProcessing {len(tradeflows)} trade flows: {', '.join(tradeflows)}")
        
        for tradeflow in tradeflows:
            print(f"\n{'='*60}")
            print(f"Processing {tradeflow.upper()} trade flows")
            print(f"{'='*60}")
            
            self.current_tradeflow = tradeflow
            self.process_bea_enhanced_tradeflow(tradeflow)
        
        # Generate comprehensive validation report
        self._generate_validation_report()
        
        total_time = time.time() - start_time
        print(f"\nCompleted all US-BEA trade flows in {total_time:.1f} seconds")
        
    def process_bea_enhanced_tradeflow(self, tradeflow):
        """Enhanced processing pipeline for single tradeflow"""
        flow_start = time.time()
        
        # Phase 1: Generate base trade data (with optimization)
        print(f"\nPhase 1: Checking/generating base {tradeflow} trade data...")
        base_data_exists = self._generate_base_trade_data(tradeflow)
        
        # Stop early if trade.csv still doesn't exist — nothing useful can be produced
        original_tradeflow = self.config['TRADEFLOW']
        self.config['TRADEFLOW'] = tradeflow
        trade_file = Path(get_file_path(self.config, 'industryflow'))
        self.config['TRADEFLOW'] = original_tradeflow
        if not trade_file.exists():
            print(f"\n⛔ trade.csv not found at {trade_file}")
            print(f"   Run ~/env/bin/python3 trade.py (with TRADEFLOW={tradeflow}) to generate it first.")
            print(f"   Stopping — no output files will be created for {tradeflow}.")
            return

        # Phase 2: BEA API data enhancement
        print(f"\nPhase 2: Enhancing with US-BEA API data...")
        self._enhance_with_bea_data(tradeflow)
        
        # Phase 3: State-level analysis (logical order based on tradeflow)
        if tradeflow == 'domestic':
            print(f"\nPhase 3: US state-to-state domestic flow analysis...")
            self._analyze_state_domestic_flows()
        elif tradeflow == 'exports':
            print(f"\nPhase 3: US state export competitiveness analysis...")
            self._analyze_state_export_competitiveness()
        elif tradeflow == 'imports':
            print(f"\nPhase 3: US import dependency analysis...")
            self._analyze_import_dependency()
            
        # Phase 4: FEDEFL integration (after trade data is established)
        print(f"\nPhase 4: US-FEDEFL flow integration...")
        self._integrate_fedefl_flows()
        
        # Phase 5: Generate enhanced output tables
        print(f"\nPhase 5: Generating US-BEA relational output tables...")
        self._generate_enhanced_output_tables(tradeflow)
        
        flow_time = time.time() - flow_start
        status = "Used existing" if base_data_exists else "Generated new"
        print(f"Completed US-BEA {tradeflow} processing in {flow_time:.1f} seconds ({status} base data)")
        
    def _generate_base_trade_data(self, tradeflow):
        """Generate base trade data with file existence optimization"""

        # Update config for current tradeflow to get correct file path
        original_tradeflow = self.config['TRADEFLOW']
        self.config['TRADEFLOW'] = tradeflow

        try:
            # Check if trade.csv already exists for this year/country/tradeflow
            trade_file_str = get_file_path(self.config, 'industryflow')
            trade_file = Path(trade_file_str)

            if trade_file.exists() and not self.force_regeneration:
                file_size = trade_file.stat().st_size / (1024*1024)
                print(f"    ✅ Found existing trade.csv for {self.config['YEAR']}/{self.config['COUNTRY']}/{tradeflow}")
                print(f"    📁 File: {trade_file} ({file_size:.1f} MB)")
                print(f"    ⏭️ Skipping regeneration (use --force-regen to override)")
                return True

            # Generate new file
            print(f"    🔄 No existing trade.csv found - generating new file")
            print(f"    🔄 Processing {tradeflow} for {self.config['YEAR']}/{self.config['COUNTRY']}...")

            # Resolve current country string for the env override
            country_cfg = self.config['COUNTRY']
            if isinstance(country_cfg, dict):
                country_str = country_cfg.get('current') or country_cfg.get('list', 'US').split(',')[0].strip()
            else:
                country_str = str(country_cfg).split(',')[0].strip()

            # Set environment variable overrides so ExiobaseTradeFlow() reads the right
            # single tradeflow/country from config.yaml (config_loader.py honours these).
            os.environ['EXIOBASE_TRADEFLOW'] = tradeflow
            os.environ['EXIOBASE_COUNTRY']   = country_str

            try:
                from trade import ExiobaseTradeFlow
                processor = ExiobaseTradeFlow()
                success = processor.run_analysis()
            finally:
                os.environ.pop('EXIOBASE_TRADEFLOW', None)
                os.environ.pop('EXIOBASE_COUNTRY',   None)

            if success:
                if trade_file.exists():
                    file_size = trade_file.stat().st_size / (1024*1024)
                    print(f"    ✅ Generated new trade.csv ({file_size:.1f} MB)")
                    return False
                else:
                    print(f"    ⚠️ Warning: Expected file not found after generation: {trade_file}")
                    return False
            else:
                print(f"    ❌ Failed to generate base {tradeflow} trade data")
                return False

        except Exception as e:
            print(f"    ❌ Error in base data generation: {e}")
            return False
        finally:
            self.config['TRADEFLOW'] = original_tradeflow
    
    def _enhance_with_bea_data(self, tradeflow):
        """Enhance trade data with US-BEA API data"""

        # Get relevant BEA datasets based on tradeflow
        if tradeflow == 'imports':
            self._fetch_bea_imports_data()
        elif tradeflow == 'exports':
            self._fetch_bea_exports_data()
        elif tradeflow == 'domestic':
            self._fetch_bea_domestic_data()
            # interstate.csv for domestic is generated in Phase 3 from state-pair disaggregation
            self._create_interstate_csvfiles()
        
    def _fetch_bea_imports_data(self):
        """Fetch BEA imports data from API"""
        print("  Fetching US-BEA imports data...")
        
        try:
            response = self.bea_client.get_international_trade_data(
                year=self.config['YEAR'], 
                trade_direction='Imports'
            )
            self.bea_imports_data = self.bea_client.process_trade_response(response)
            print(f"    Retrieved {len(self.bea_imports_data)} import records")
            
        except Exception as e:
            print(f"    US-BEA imports data unavailable: {e}")
            self.bea_imports_data = pd.DataFrame()
            self.validation_issues.append(f"US-BEA imports API error: {e}")
    
    def _fetch_bea_exports_data(self):
        """Fetch BEA exports data including state-level data"""
        print("  Fetching US-BEA exports data...")
        
        try:
            # National exports
            response = self.bea_client.get_international_trade_data(
                year=self.config['YEAR'],
                trade_direction='Exports'
            )
            self.bea_exports_data = self.bea_client.process_trade_response(response)
            print(f"    Retrieved {len(self.bea_exports_data)} export records")
            
            # State-level exports
            self._fetch_state_exports_data()
            
        except Exception as e:
            print(f"    US-BEA exports data unavailable: {e}")
            self.bea_exports_data = pd.DataFrame()
            self.validation_issues.append(f"US-BEA exports API error: {e}")
    
    def _fetch_state_exports_data(self):
        """Fetch state-level export data from BEA"""
        print("  Fetching US state-level exports data...")
        
        try:
            response = self.bea_client.get_state_exports_data(
                year=self.config['YEAR'],
                state_code='ALL'
            )
            self.bea_state_exports = self.bea_client.process_state_response(response)
            print(f"    Retrieved state export data for {len(self.bea_state_exports)} records")
            
        except Exception as e:
            print(f"    US state exports data unavailable: {e}")
            self.bea_state_exports = pd.DataFrame()
            self.validation_issues.append(f"US-BEA state exports API error: {e}")
    
    def _fetch_bea_domestic_data(self):
        """Fetch BEA domestic economic data"""
        print("  Fetching US-BEA domestic data...")
        
        try:
            # Input-Output Tables
            response = self.bea_client.get_input_output_data(
                year=self.config['YEAR'],
                table_id='Summary'
            )
            self.bea_domestic_data = self.bea_client.process_io_response(response)
            print(f"    Retrieved domestic I-O data")
            
        except Exception as e:
            print(f"    US-BEA domestic data unavailable: {e}")
            self.bea_domestic_data = pd.DataFrame()
            self.validation_issues.append(f"US-BEA domestic API error: {e}")
    
    def _create_interstate_csvfiles(self):
        """Create enhanced trade detail with US-BEA data integration"""
        print("  📝 Creating US-BEA trade detail integration...")
        
        # Update config for current tradeflow
        original_tradeflow = self.config['TRADEFLOW']
        self.config['TRADEFLOW'] = self.current_tradeflow
        
        try:
            # Load base trade data
            trade_file_str = get_file_path(self.config, 'industryflow')
            trade_file = Path(trade_file_str)  # Convert to Path object
            
            if not trade_file.exists():
                print(f"    ⚠️ Base trade file not found: {trade_file}")
                return
                
            base_trade = pd.read_csv(trade_file)
            
            # Create enhanced trade detail table
            enhanced_detail = base_trade.copy()
            
            # Add US-BEA-specific enhancements
            if self.current_tradeflow == 'imports' and hasattr(self, 'bea_imports_data'):
                enhanced_detail = self._merge_bea_imports(enhanced_detail)
            elif self.current_tradeflow == 'exports' and hasattr(self, 'bea_exports_data'):
                enhanced_detail = self._merge_bea_exports(enhanced_detail)
            elif self.current_tradeflow == 'domestic' and hasattr(self, 'bea_domestic_data'):
                enhanced_detail = self._merge_bea_domestic(enhanced_detail)
            
            # Rename trade_id → interstate_id as the primary key for the interstate table
            if 'trade_id' in enhanced_detail.columns:
                enhanced_detail = enhanced_detail.rename(columns={'trade_id': 'interstate_id'})

            # Save enhanced detail
            output_file = trade_file.parent / 'interstate.csv'
            output_file.parent.mkdir(parents=True, exist_ok=True)
            enhanced_detail.to_csv(output_file, index=False)
            print(f"    ✅ Created interstate.csv: {output_file}")
            
        except Exception as e:
            print(f"    ❌ Error creating BEA trade detail: {e}")
        finally:
            # Restore original config
            self.config['TRADEFLOW'] = original_tradeflow
    
    def _merge_bea_imports(self, base_trade):
        """Merge US-BEA imports data with base trade"""
        enhanced = base_trade.copy()
        
        # Add US-BEA-specific columns
        enhanced['commodity_code'] = ''
        enhanced['industry_code'] = ''
        enhanced['trade_balance'] = 0.0
        enhanced['import_value'] = enhanced['amount']
        enhanced['export_value'] = 0.0
        
        return enhanced
    
    def _merge_bea_exports(self, base_trade):
        """Merge US-BEA exports data with base trade"""
        enhanced = base_trade.copy()
        
        # Add US-BEA-specific columns
        enhanced['commodity_code'] = ''
        enhanced['industry_code'] = ''
        enhanced['trade_balance'] = enhanced['amount']
        enhanced['import_value'] = 0.0
        enhanced['export_value'] = enhanced['amount']
        
        return enhanced
    
    def _merge_bea_domestic(self, base_trade):
        """Merge US-BEA domestic data with base trade"""
        enhanced = base_trade.copy()
        
        # Add domestic-specific columns
        enhanced['commodity_code'] = ''
        enhanced['industry_code'] = ''
        enhanced['economic_multiplier'] = 1.0
        
        return enhanced
    
    def _analyze_state_domestic_flows(self):
        """Analyze US state-to-state domestic trade flows"""
        print("  Analyzing US state-to-state flows...")

        # Update config for current tradeflow
        original_tradeflow = self.config['TRADEFLOW']
        self.config['TRADEFLOW'] = self.current_tradeflow

        try:
            # Load base trade data
            trade_file_str = get_file_path(self.config, 'industryflow')
            trade_file = Path(trade_file_str)

            if trade_file.exists():
                base_trade = pd.read_csv(trade_file)

                # Load Exiobase satellite matrix so factor_id is added to every state-pair row.
                # The zip lives two directories above bea/ (i.e. tradeflow/exiobase_data/).
                exiobase_zip = (
                    Path(__file__).parents[1]
                    / 'exiobase_data'
                    / f'IOT_{self.config["YEAR"]}_pxp.zip'
                )
                if exiobase_zip.exists():
                    print("    Loading Exiobase satellite data for factor_id assignment...")
                    self.state_analyzer.load_exiobase_satellite(exiobase_zip)
                else:
                    print(f"    Exiobase zip not found at {exiobase_zip}")
                    print("    interstate_factor.csv will be generated without factor_id")

                # Use US state analyzer to disaggregate flows
                bea_data = getattr(self, 'bea_domestic_data', pd.DataFrame())
                state_flows = self.state_analyzer.disaggregate_domestic_flows(
                    base_trade, bea_data
                )
                
                # Calculate comprehensive US state impacts
                state_impacts = self.state_analyzer.calculate_state_industry_impacts(state_flows)
                
                # Save results
                output_path = trade_file.parent
                output_path.mkdir(parents=True, exist_ok=True)

                has_satellite = bool(getattr(self.state_analyzer, '_satellite_data', None))
                use_partial = self.config['PROCESSING'].get('use_partial_factors_interstate', True)
                partial_limit = self.config['PROCESSING'].get('partial_factor_limit_interstate', 50)

                if has_satellite and '_industry1' in state_flows.columns:
                    # Build integer interstate_id from unique state-pair combinations
                    unique_pairs = (
                        state_flows[['interstate_id', 'trade_id', '_origin_state', '_destination_state',
                                     '_industry1', 'state_industry_code', 'level']]
                        .drop_duplicates(subset=['interstate_id'])
                        .reset_index(drop=True)
                    )
                    unique_pairs.insert(0, 'interstate_id_int', range(1, len(unique_pairs) + 1))
                    id_map = dict(zip(unique_pairs['interstate_id'], unique_pairs['interstate_id_int']))

                    # Overwrite interstate.csv with proper state-pair rows and integer interstate_id
                    interstate_df = pd.DataFrame({
                        'interstate_id': unique_pairs['interstate_id_int'],
                        'trade_id':      unique_pairs['trade_id'],
                        'year':          self.config['YEAR'],
                        'region1':       unique_pairs['_origin_state'],
                        'region2':       unique_pairs['_destination_state'],
                        'industry1':     unique_pairs['_industry1'],
                        'state_industry_code': unique_pairs['state_industry_code'],
                        'amount':        unique_pairs['level'],
                    })
                    interstate_df.to_csv(output_path / 'interstate.csv', index=False)
                    print(f"    ✅ Created interstate.csv ({len(interstate_df)} state-pair rows)")

                    # Map string interstate_id → integer in state_flows
                    state_flows['interstate_id'] = state_flows['interstate_id'].map(id_map)

                    # Compute level = level × coefficient
                    state_flows['level'] = state_flows['level'] * state_flows['coefficient']

                    # Round: 3 decimals for water/air_emissions, 0 for other extensions
                    factors_ref_path = Path(get_reference_file_path(self.config, 'factors'))
                    if not factors_ref_path.exists():
                        print(f"    ❌ factor.csv not found at {factors_ref_path} — cannot apply extension-based rounding. Stopping.")
                        return
                    ext_map = pd.read_csv(factors_ref_path)[['factor_id', 'extension']]
                    state_flows = state_flows.merge(ext_map, on='factor_id', how='left')
                    fine = state_flows['extension'].isin(('water', 'air_emissions'))
                    missing = state_flows['extension'].isna()
                    state_flows.loc[fine,             'level'] = state_flows.loc[fine,             'level'].round(3)
                    state_flows.loc[missing,          'level'] = state_flows.loc[missing,          'level'].round(3)
                    state_flows.loc[~fine & ~missing, 'level'] = state_flows.loc[~fine & ~missing, 'level'].round(0).astype(int)
                    state_flows = state_flows.drop(columns=['extension'])

                    factor_cols = ['interstate_id', 'factor_id', 'level']

                    # Optionally generate large file (all 721 factors)
                    if not use_partial:
                        lg_file = self.config['FILES'].get('interstate_factor_lg', 'interstate_factor_lg.csv')
                        state_flows[factor_cols].to_csv(output_path / lg_file, index=False)
                        print(f"    ✅ Created {lg_file} ({len(state_flows)} rows, all factors)")

                    # Filter to top partial_limit factors per industry and save
                    satellite = self.state_analyzer._satellite_data
                    lookup_rows = [
                        {'_industry1': iid, 'factor_id': fid}
                        for iid, entries in satellite.items()
                        for fid, _ in entries[:partial_limit]
                    ]
                    if lookup_rows:
                        top_factors_df = pd.DataFrame(lookup_rows)
                        state_flows_limited = state_flows.merge(
                            top_factors_df, on=['_industry1', 'factor_id'], how='inner'
                        )
                    else:
                        state_flows_limited = state_flows.copy()

                    state_flows_limited[factor_cols].to_csv(output_path / 'interstate_factor.csv', index=False)
                    print(f"    ✅ Created interstate_factor.csv ({len(state_flows_limited)} rows, {partial_limit} Selected Factors)")

                else:
                    # No satellite data — drop internal cols and save as-is
                    internal_cols = ['_origin_state', '_destination_state', '_industry1']
                    state_flows_out = state_flows.drop(
                        columns=[c for c in internal_cols if c in state_flows.columns]
                    )
                    state_flows_out.to_csv(output_path / 'interstate_factor.csv', index=False)
                    print(f"    ✅ Created interstate_factor.csv ({len(state_flows_out)} rows)")

                state_impacts.to_csv(output_path / 'state_industry_impacts.csv', index=False)
                print(f"    Created US state domestic flow analysis")
            else:
                print(f"    Base trade file not found: {trade_file}")
        except Exception as e:
            print(f"    Error in state domestic analysis: {e}")
        finally:
            # Restore original config
            self.config['TRADEFLOW'] = original_tradeflow
    
    def _analyze_state_export_competitiveness(self):
        """Analyze US state export competitiveness"""
        print("  Analyzing US export competitiveness...")
        
        # Update config for current tradeflow
        original_tradeflow = self.config['TRADEFLOW']
        self.config['TRADEFLOW'] = self.current_tradeflow
        
        try:
            # Load export trade data
            trade_file_str = get_file_path(self.config, 'industryflow')
            trade_file = Path(trade_file_str)
            
            if trade_file.exists():
                export_trade = pd.read_csv(trade_file)
                
                # Use US state analyzer for competitiveness analysis
                bea_data = getattr(self, 'bea_exports_data', pd.DataFrame())
                competitiveness = self.state_analyzer.analyze_export_competitiveness(
                    export_trade, bea_data
                )
                
                # Save results
                output_path = trade_file.parent
                output_path.mkdir(parents=True, exist_ok=True)
                competitiveness.to_csv(output_path / 'export_competitiveness.csv', index=False)
                
                print(f"    Created US export competitiveness analysis")
            else:
                print(f"    Export trade file not found: {trade_file}")
        except Exception as e:
            print(f"    Error in export competitiveness analysis: {e}")
        finally:
            # Restore original config
            self.config['TRADEFLOW'] = original_tradeflow
    
    def _analyze_import_dependency(self):
        """Analyze US import dependency and vulnerabilities"""
        print("  Analyzing US import dependencies...")
        
        # Update config for current tradeflow
        original_tradeflow = self.config['TRADEFLOW']
        self.config['TRADEFLOW'] = self.current_tradeflow
        
        try:
            # Load import trade data
            trade_file_str = get_file_path(self.config, 'industryflow')
            trade_file = Path(trade_file_str)
            
            if trade_file.exists():
                import_trade = pd.read_csv(trade_file)
                
                # Use US state analyzer for dependency analysis
                bea_data = getattr(self, 'bea_imports_data', pd.DataFrame())
                dependency = self.state_analyzer.analyze_import_dependency(
                    import_trade, bea_data
                )
                
                # Save results
                output_path = trade_file.parent
                output_path.mkdir(parents=True, exist_ok=True)
                dependency.to_csv(output_path / 'import_dependency.csv', index=False)
                
                print(f"    Created US import dependency analysis")
            else:
                print(f"    Import trade file not found: {trade_file}")
        except Exception as e:
            print(f"    Error in import dependency analysis: {e}")
        finally:
            # Restore original config
            self.config['TRADEFLOW'] = original_tradeflow
    
    def _integrate_fedefl_flows(self):
        """Integrate US-FEDEFL flow data"""
        print("  Integrating US-FEDEFL flows...")
        
        try:
            # Load comprehensive FEDEFL flows
            factors_file_str = get_reference_file_path(self.config, 'factors')
            output_path = Path(factors_file_str).parent
            
            flow_data = self.fedefl_integrator.create_comprehensive_flow_table(output_path)
            
            # Validate flow completeness with trade factors
            factors_file = Path(factors_file_str)
            if factors_file.exists():
                factors = pd.read_csv(factors_file)
                self.fedefl_integrator.validate_flow_completeness(factors, output_path)
            
            print(f"    Created US-FEDEFL flow integration with {len(flow_data)} flows")
            
        except Exception as e:
            print(f"    US-FEDEFL integration failed: {e}")
            self.validation_issues.append(f"US-FEDEFL integration error: {e}")
    
    def _generate_enhanced_output_tables(self, tradeflow):
        """Generate all US-BEA enhanced output tables"""
        print("  Generating US-BEA enhanced tables...")
        
        # Update config for current tradeflow
        original_tradeflow = self.config['TRADEFLOW']
        self.config['TRADEFLOW'] = self.current_tradeflow
        
        try:
            trade_file_str = get_file_path(self.config, 'industryflow')
            output_path = Path(trade_file_str).parent
            output_path.mkdir(parents=True, exist_ok=True)

            # Create US trade price indices table
            self._create_trade_price_indices(output_path)
            
            # Note: Using existing industry.csv file instead of generating bea_industry_mapping.csv Delete: https://github.com/ModelEarth/trade-data/blob/main/year/2019/US/domestic/bea_industry_mapping.csv
            
            # Create US state reference data
            self.state_analyzer.create_state_reference_data(output_path)
            
            print(f"    Generated US-BEA enhanced output tables")
        except Exception as e:
            print(f"    Error generating enhanced tables: {e}")
        finally:
            # Restore original config
            self.config['TRADEFLOW'] = original_tradeflow
    
    def _create_trade_price_indices(self, output_path):
        """Create US trade price indices table"""
        # Basic price indices structure
        price_indices = pd.DataFrame({
            'trade_id': [],
            'import_price_index': [],
            'export_price_index': [],
            'exchange_rate': [],
            'price_year': [],
            'currency_adjustment_factor': []
        })
        
        price_indices.to_csv(output_path / 'trade_price_indices.csv', index=False)
    
    
    def _generate_validation_report(self):
        """Generate comprehensive US-BEA validation report"""
        country_info = self.config['COUNTRY']
        if isinstance(country_info, dict):
            country = country_info.get('current', country_info.get('list', 'US'))
        else:
            country = str(country_info)
        
        # Create report directory path
        base_folder = self.config['FOLDERS']['base'].format(year=self.config['YEAR'])
        report_path = Path(base_folder) / country / 'bea-report.md'
        
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_path, 'w') as f:
            f.write(f"# BEA Trade Analysis Validation Report\n\n")
            f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Year**: {self.config['YEAR']}\n")
            f.write(f"**Country**: {country}\n")
            f.write(f"**Trade Flows**: {self.config['TRADEFLOW']}\n")
            f.write(f"**Force Regeneration**: {self.force_regeneration}\n\n")
            
            f.write("## Optimization Status\n\n")
            if self.force_regeneration:
                f.write("- Force regeneration enabled - all trade.csv files recreated\n")
            else:
                f.write("- File existence checking enabled - existing trade.csv files reused\n")
            
            f.write("\n## US Data Source Integration\n\n")
            f.write("### Exiobase Data\n")
            f.write("- Successfully processed Exiobase MRIO data\n")
            f.write("- Generated base trade flows with trade_id structure\n\n")
            
            f.write("### US-BEA API Integration\n")
            if self.validation_issues:
                f.write("- Issues encountered:\n")
                for issue in self.validation_issues:
                    f.write(f"  - {issue}\n")
            else:
                f.write("- Successfully integrated US-BEA API data\n")
            
            # Add US-BEA API usage statistics
            api_stats = self.bea_client.get_api_usage_stats()
            f.write(f"\n### BEA API Usage Statistics\n")
            f.write(f"- API calls made: {api_stats['api_calls_made']}\n")
            f.write(f"- Cache files created: {api_stats['cache_files']}\n")
            
            f.write(f"\n## BEA Enhanced Output Files Generated\n\n")
            f.write(f"### Enhanced Relational Tables\n")
            f.write(f"- `trade.csv` - Base trade flows\n")
            f.write(f"- `interstate.csv` - State-to-state trade details\n")
            f.write(f"- `interstate_factor.csv` - State-level trade flows\n")
            f.write(f"- `export_competitiveness.csv` - Export competitiveness analysis\n")
            f.write(f"- `import_dependency.csv` - Import dependency analysis\n")
            f.write(f"- `flow.csv` - FEDEFL flow details\n")
            f.write(f"- `industry.csv` - Industry mapping (using existing file from parent directory)\n") 
            f.write(f"- `state_industry_impacts.csv` - State economic impacts\n")
            f.write(f"- `trade_price_indices.csv` - Trade price indices\n\n")
        
        print(f"Generated BEA validation report: {report_path}")

def main():
    parser = argparse.ArgumentParser(description='US-BEA Enhanced Trade Flow Analysis with optimization')
    parser.add_argument('--bea-key', help='BEA API key (or use .env file)')
    parser.add_argument('--force-regen', action='store_true', 
                       help='Force regeneration of trade.csv files even if they exist')
    
    args = parser.parse_args()
    
    try:
        print("Initializing US-BEA Trade Flow Analysis...")
        processor = USBEATradeFlow(bea_api_key=args.bea_key, force_regeneration=args.force_regen)
        processor.process_all_tradeflows()
        
    except Exception as e:
        print(f"US-BEA Analysis Error: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())