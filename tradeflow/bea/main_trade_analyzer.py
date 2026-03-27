"""
State Trade Analyzer for US Trade Flow Disaggregation

Provides state-level trade flow disaggregation, economic impact calculations,
and employment multipliers for comprehensive US trade analysis.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
import re

class StateTradeAnalyzer:
    def __init__(self, config):
        self.config = config
        self.year = config['YEAR']
        
        # Load state reference data
        self.state_codes = self._load_state_codes()
        self.employment_multipliers = self._load_employment_multipliers()
        self.industry_state_mapping = self._load_industry_state_data()
        
        # Economic impact coefficients
        self.direct_job_coefficient = 1.0
        self.indirect_job_multiplier = 0.7
        self.induced_job_multiplier = 0.5
        self.output_multiplier = 2.1
        self.tax_revenue_rate = 0.12
        
    def _load_state_codes(self):
        """Load US state codes and names"""
        # Standard US state codes
        states = {
            'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
            'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
            'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
            'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas',
            'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
            'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
            'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
            'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
            'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma',
            'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
            'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
            'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
            'WI': 'Wisconsin', 'WY': 'Wyoming', 'DC': 'District of Columbia'
        }
        
        return pd.DataFrame([
            {'state_code': code, 'state_name': name} 
            for code, name in states.items()
        ])
    
    def _load_employment_multipliers(self):
        """Load industry-specific employment multipliers"""
        # Industry employment multipliers (simplified - in practice would come from BEA data)
        multipliers = {
            'manufacturing': {'direct': 1.0, 'indirect': 0.8, 'induced': 0.6},
            'agriculture': {'direct': 1.0, 'indirect': 0.5, 'induced': 0.4},
            'services': {'direct': 1.0, 'indirect': 0.6, 'induced': 0.5},
            'mining': {'direct': 1.0, 'indirect': 0.9, 'induced': 0.7},
            'construction': {'direct': 1.0, 'indirect': 0.7, 'induced': 0.5},
            'utilities': {'direct': 1.0, 'indirect': 0.4, 'induced': 0.3},
            'transportation': {'direct': 1.0, 'indirect': 0.6, 'induced': 0.5},
            'default': {'direct': 1.0, 'indirect': 0.7, 'induced': 0.5}
        }
        
        return multipliers
    
    def _load_industry_state_data(self):
        """Load industry-state mapping and specialization data"""
        # State specialization indices (simplified example)
        # In practice, this would come from BEA regional data
        specializations = {}
        
        # Major state specializations
        state_specializations = {
            'CA': ['technology', 'agriculture', 'entertainment'],
            'TX': ['energy', 'chemicals', 'agriculture'], 
            'NY': ['finance', 'services', 'manufacturing'],
            'IL': ['manufacturing', 'agriculture', 'transportation'],
            'FL': ['agriculture', 'tourism', 'aerospace'],
            'WA': ['technology', 'aerospace', 'agriculture'],
            'MI': ['automotive', 'manufacturing', 'agriculture'],
            'OH': ['manufacturing', 'agriculture', 'services'],
            'PA': ['manufacturing', 'energy', 'agriculture'],
            'NC': ['manufacturing', 'agriculture', 'technology']
        }
        
        return state_specializations
    
    def load_exiobase_satellite(self, exiobase_zip_path):
        """
        Load Exiobase S matrix (environmental intensity per unit output) for US sectors.
        Populates self._satellite_data: dict of industry_id -> list of (factor_id, coefficient).
        Factor IDs are assigned by row position across extensions (same as factors.py).
        """
        try:
            import pymrio
        except ImportError:
            print("    pymrio not available — skipping satellite factor loading")
            self._satellite_data = {}
            return {}

        exiobase_zip_path = Path(exiobase_zip_path)
        if not exiobase_zip_path.exists():
            print(f"    Exiobase zip not found: {exiobase_zip_path} — skipping satellite factor loading")
            self._satellite_data = {}
            return {}

        print(f"    Loading Exiobase satellite matrix from {exiobase_zip_path.name}...")
        exio_model = pymrio.parse_exiobase3(str(exiobase_zip_path)).calc_all()

        # Build stressor → factor_id mapping (same extension order and row order as factors.py)
        extensions = ['air_emissions', 'employment', 'energy', 'land', 'material', 'water']
        stressor_to_fid = {}
        fid = 1
        for ext_name in extensions:
            if hasattr(exio_model, ext_name):
                ext = getattr(exio_model, ext_name)
                if hasattr(ext, 'F'):
                    for stressor in ext.F.index.tolist():
                        stressor_to_fid[stressor] = fid
                        fid += 1

        # Build sector_name → industry_id mapping (same algorithm as create_sector_mapping.py)
        sectors = exio_model.Z.index.get_level_values('sector').unique()
        used_ids = set()
        sector_to_iid = {}
        for i, sector in enumerate(sectors):
            iid = self._make_industry_id(str(sector), i, used_ids)
            sector_to_iid[str(sector)] = iid

        threshold = self.config.get('PROCESSING', {}).get('min_impact_threshold', 0.001)

        satellite_data = {}  # industry_id → list of (factor_id, coefficient), all factors meeting threshold

        for ext_name in extensions:
            if hasattr(exio_model, ext_name):
                ext = getattr(exio_model, ext_name)
                if not hasattr(ext, 'S'):
                    continue
                try:
                    us_S = ext.S.xs('US', level='region', axis=1)
                except KeyError:
                    continue

                for sector in us_S.columns:
                    iid = sector_to_iid.get(str(sector))
                    if not iid:
                        continue
                    entries = [
                        (stressor_to_fid[stressor], float(us_S.loc[stressor, sector]))
                        for stressor in us_S.index
                        if stressor in stressor_to_fid and abs(float(us_S.loc[stressor, sector])) >= threshold
                    ]
                    if entries:
                        if iid not in satellite_data:
                            satellite_data[iid] = []
                        satellite_data[iid].extend(entries)

        # Sort each industry's full factor list globally by magnitude (descending).
        # This allows callers to slice [:N] to get the top-N selected factors.
        for iid in satellite_data:
            satellite_data[iid].sort(key=lambda x: abs(x[1]), reverse=True)

        self._satellite_data = satellite_data
        print(f"    Satellite data loaded: {len(satellite_data)} US industries with factor coefficients")
        return satellite_data

    def _make_industry_id(self, sector_str, index, used_ids):
        """Generate 5-char industry ID from sector name (mirrors create_sector_mapping.py logic)."""
        clean = re.sub(r'\b(and|of|related|to|services|products|nec|other)\b', '', sector_str, flags=re.IGNORECASE)
        clean = re.sub(r'[^\w\s]', '', clean).strip()
        words = clean.split()
        cid = clean.replace(' ', '')[:5].upper()
        if len(cid) < 5 and len(words) > 1:
            acr = ''.join(w[0] for w in words if w)[:3].upper()
            cid = (acr + clean.replace(' ', '')[len(acr):])[:5].upper()
        if len(cid) < 5:
            cid = (cid + str(index).zfill(5 - len(cid)))[:5]
        orig = cid
        c = 1
        while cid in used_ids:
            cid = (orig[:4] + str(c)) if c < 10 else (orig[:3] + str(c).zfill(2))
            c += 1
        used_ids.add(cid)
        return cid

    def disaggregate_domestic_flows(self, base_trade_df, bea_state_data=None):
        """
        Disaggregate national domestic flows to state-to-state flows.

        When self._satellite_data is populated (via load_exiobase_satellite), each
        state-pair flow is expanded to one row per Exiobase factor, with factor_id
        and coefficient columns added.  Employment impacts are omitted in that case
        because employment is already captured as Exiobase factor rows.

        Args:
            base_trade_df: Base trade DataFrame with domestic flows
            bea_state_data: Optional BEA state-level data for enhancement

        Returns:
            DataFrame with state-level domestic trade flows
        """
        print("    🗺️ Disaggregating domestic flows to state level...")

        state_flows = []

        for _, trade_row in base_trade_df.iterrows():
            state_disagg = self._disaggregate_single_flow(trade_row, bea_state_data)
            state_flows.extend(state_disagg)

        state_df = pd.DataFrame(state_flows)

        # Employment impacts are calculated only when satellite factor data is absent;
        # when factor_id rows are present, employment is already encoded as Exiobase factors.
        has_satellite = bool(getattr(self, '_satellite_data', None))
        if not state_df.empty and not has_satellite:
            state_df = self._calculate_employment_impacts(state_df)

        print(f"      ✅ Created {len(state_df)} state-to-state flow records")
        return state_df
    
    def _disaggregate_single_flow(self, trade_row, bea_data=None):
        """Disaggregate a single trade flow to state level.

        When self._satellite_data is populated, emits one row per (state-pair, factor_id)
        using Exiobase S-matrix coefficients for the trade row's industry1 sector.
        Otherwise emits one aggregate row per state-pair.
        """
        flows = []

        # Broad industry category used for state allocation weights
        industry = self._categorize_industry(trade_row.get('industry1', ''))
        producing_states = self._get_producing_states(industry)
        consuming_states = self._get_consuming_states(industry)
        total_value = float(trade_row.get('amount', 0))

        # Satellite factor data keyed by the actual Exiobase industry_id (5-char)
        satellite = getattr(self, '_satellite_data', None)
        industry_id = str(trade_row.get('industry1', ''))
        factor_entries = satellite.get(industry_id, []) if satellite else []

        for origin_state in producing_states:
            for dest_state in consuming_states:
                if origin_state == dest_state:
                    continue

                flow_share = self._calculate_state_flow_share(
                    origin_state, dest_state, industry, bea_data
                )
                if flow_share <= 0:
                    continue

                level = total_value * flow_share
                interstate_id = f"{self.year}-US-{origin_state}-US-{dest_state}-{industry}"

                if factor_entries:
                    # Expand to one row per Exiobase factor
                    for fid, coeff in factor_entries:
                        flows.append({
                            'interstate_id': interstate_id,
                            'trade_id': trade_row.get('trade_id', ''),
                            'factor_id': fid,
                            'coefficient': coeff,
                            'state_industry_code': industry,
                            'level': level,
                            'flow_type': 'inter_state',
                            'employment_impact': 0,
                            # Internal only — dropped before CSV write
                            '_origin_state': origin_state,
                            '_destination_state': dest_state,
                            '_industry1': industry_id,
                        })
                else:
                    # Aggregate row (no satellite data for this industry / satellite not loaded)
                    flows.append({
                        'interstate_id': interstate_id,
                        'trade_id': trade_row.get('trade_id', ''),
                        'state_industry_code': industry,
                        'level': level,
                        'flow_type': 'inter_state',
                        'employment_impact': 0,
                        '_origin_state': origin_state,
                        '_destination_state': dest_state,
                    })

        return flows
    
    def _categorize_industry(self, industry_code):
        """Categorize industry code into broad category"""
        if not industry_code:
            return 'services'
        
        # Map industry codes to categories (simplified)
        if industry_code.startswith('31') or industry_code.startswith('32') or industry_code.startswith('33'):
            return 'manufacturing'
        elif industry_code.startswith('11'):
            return 'agriculture'
        elif industry_code.startswith('21'):
            return 'mining'
        elif industry_code.startswith('22'):
            return 'utilities'
        elif industry_code.startswith('23'):
            return 'construction'
        elif industry_code.startswith('48') or industry_code.startswith('49'):
            return 'transportation'
        else:
            return 'services'
    
    def _get_producing_states(self, industry):
        """Get states that are major producers in this industry"""
        # Return states based on industry specialization
        producing_states = []
        
        for state, specializations in self.industry_state_mapping.items():
            if industry in specializations:
                producing_states.append(state)
        
        # Add default major states if none found
        if not producing_states:
            producing_states = ['CA', 'TX', 'NY', 'IL', 'FL', 'OH', 'PA', 'MI']
        
        return producing_states
    
    def _get_consuming_states(self, industry):
        """Get states that are major consumers in this industry"""
        # For simplicity, use all major states as consumers
        # In practice, this would be based on consumption patterns
        return ['CA', 'TX', 'NY', 'FL', 'IL', 'PA', 'OH', 'MI', 'GA', 'NC', 'NJ', 'VA', 'WA', 'AZ', 'MA', 'IN', 'TN', 'MO', 'MD', 'WI']
    
    def _calculate_state_flow_share(self, origin, destination, industry, bea_data):
        """Calculate the share of flow between two states"""
        # Base share using population/GDP proxies
        base_shares = {
            'CA': 0.12, 'TX': 0.09, 'FL': 0.06, 'NY': 0.06, 'PA': 0.04, 
            'IL': 0.04, 'OH': 0.04, 'GA': 0.03, 'NC': 0.03, 'MI': 0.03
        }
        
        origin_weight = base_shares.get(origin, 0.01)
        dest_weight = base_shares.get(destination, 0.01)
        
        # Apply industry specialization modifier
        specialization_bonus = 1.0
        if origin in self.industry_state_mapping:
            if industry in self.industry_state_mapping[origin]:
                specialization_bonus = 1.5
        
        # Calculate flow share (simplified allocation)
        flow_share = (origin_weight * dest_weight * specialization_bonus) / 100
        
        return min(flow_share, 0.1)  # Cap at 10% of total flow
    
    def _calculate_employment_impacts(self, state_flows_df):
        """Calculate employment impacts for state flows"""
        if state_flows_df.empty:
            return state_flows_df
        
        print("    👥 Calculating employment impacts...")
        
        for index, row in state_flows_df.iterrows():
            industry = row['state_industry_code']
            level = row['level']
            
            # Get employment multipliers for industry
            multipliers = self.employment_multipliers.get(industry, 
                                                        self.employment_multipliers['default'])
            
            # Calculate employment impact (jobs per million dollars)
            jobs_per_million = 15.0  # Base jobs per million dollars (varies by industry)
            
            if industry == 'manufacturing':
                jobs_per_million = 12.0
            elif industry == 'agriculture':
                jobs_per_million = 20.0
            elif industry == 'services':
                jobs_per_million = 18.0
            elif industry == 'construction':
                jobs_per_million = 25.0
            
            # Calculate total employment impact
            employment_impact = (level / 1000000) * jobs_per_million
            state_flows_df.loc[index, 'employment_impact'] = employment_impact
        
        return state_flows_df
    
    def calculate_state_industry_impacts(self, state_flows_df):
        """Calculate comprehensive state-industry economic impacts"""
        if state_flows_df.empty:
            return pd.DataFrame()
        
        print("    📊 Calculating state industry impacts...")
        
        # Aggregate flows by destination state and industry
        state_industry_agg = state_flows_df.groupby(['_destination_state', 'state_industry_code']).agg({
            'level': 'sum',
            'employment_impact': 'sum'
        }).reset_index()
        
        impacts = []
        
        for _, row in state_industry_agg.iterrows():
            state = row['_destination_state']
            industry = row['state_industry_code']
            level = row['level']
            direct_jobs = row['employment_impact']
            
            # Get multipliers
            multipliers = self.employment_multipliers.get(industry,
                                                        self.employment_multipliers['default'])
            
            # Calculate indirect and induced employment
            indirect_jobs = direct_jobs * multipliers['indirect']
            induced_jobs = direct_jobs * multipliers['induced']
            
            # Calculate output and tax impacts
            total_output_impact = level * self.output_multiplier
            tax_revenue_impact = total_output_impact * self.tax_revenue_rate
            
            impacts.append({
                'region': f'US-{state}',
                'industry_code': industry,
                'direct_jobs': direct_jobs,
                'indirect_jobs': indirect_jobs, 
                'induced_jobs': induced_jobs,
                'total_output_impact': total_output_impact,
                'tax_revenue_impact': tax_revenue_impact
            })
        
        impacts_df = pd.DataFrame(impacts)
        print(f"      ✅ Calculated impacts for {len(impacts_df)} state-industry combinations")
        
        return impacts_df
    
    def analyze_export_competitiveness(self, export_flows_df, bea_exports_data=None):
        """Analyze export competitiveness by state and industry"""
        print("    📈 Analyzing export competitiveness...")
        
        if export_flows_df.empty:
            return pd.DataFrame()
        
        competitiveness_data = []
        
        # Group by industry for analysis
        industry_groups = export_flows_df.groupby(['industry1', 'region2'])
        
        for (industry, destination), group in industry_groups:
            total_exports = group['amount'].sum()
            
            # Calculate competitiveness metrics
            # Revealed Comparative Advantage (simplified)
            rca = self._calculate_rca(industry, destination, total_exports)
            
            # Export sophistication index (simplified)
            sophistication = self._calculate_sophistication(industry)
            
            # Market share (simplified)
            market_share = self._calculate_market_share(industry, destination, total_exports)
            
            # Growth rate (would need historical data - using placeholder)
            growth_rate = np.random.normal(0.02, 0.05)  # Placeholder
            
            for _, row in group.iterrows():
                competitiveness_data.append({
                    'trade_id': row.get('trade_id', ''),
                    'revealed_comparative_advantage': rca,
                    'export_sophistication_index': sophistication,
                    'market_share': market_share,
                    'growth_rate': growth_rate
                })
        
        competitiveness_df = pd.DataFrame(competitiveness_data)
        
        # Ensure trade_id column is properly named and positioned first
        if not competitiveness_df.empty:
            cols = ['trade_id'] + [col for col in competitiveness_df.columns if col != 'trade_id']
            competitiveness_df = competitiveness_df[cols]
        
        print(f"      ✅ Analyzed competitiveness for {len(competitiveness_df)} export flows")
        
        return competitiveness_df
    
    def analyze_import_dependency(self, import_flows_df, bea_imports_data=None):
        """Analyze import dependency and supply chain vulnerabilities"""
        print("    🔗 Analyzing import dependencies...")
        
        if import_flows_df.empty:
            return pd.DataFrame()
        
        dependency_data = []
        
        # Group by industry and origin
        industry_groups = import_flows_df.groupby(['industry2', 'region1'])
        
        for (industry, origin), group in industry_groups:
            total_imports = group['amount'].sum()
            
            # Calculate dependency metrics
            penetration_ratio = self._calculate_import_penetration(industry, total_imports)
            vulnerability = self._assess_supply_chain_vulnerability(origin, industry)
            alternative_suppliers = self._count_alternative_suppliers(industry, origin, import_flows_df)
            strategic_importance = self._assess_strategic_importance(industry)
            
            for _, row in group.iterrows():
                dependency_data.append({
                    'trade_id': row.get('trade_id', ''),
                    'import_penetration_ratio': penetration_ratio,
                    'supply_chain_vulnerability': vulnerability,
                    'alternative_suppliers': alternative_suppliers,
                    'strategic_importance': strategic_importance
                })
        
        dependency_df = pd.DataFrame(dependency_data)
        
        # Ensure trade_id column is properly named and positioned first
        if not dependency_df.empty:
            cols = ['trade_id'] + [col for col in dependency_df.columns if col != 'trade_id']
            dependency_df = dependency_df[cols]
        
        print(f"      ✅ Analyzed dependencies for {len(dependency_df)} import flows")
        
        return dependency_df
    
    def _calculate_rca(self, industry, destination, exports):
        """Calculate Revealed Comparative Advantage"""
        # Simplified RCA calculation
        # In practice: (Xij/Xit) / (Xwj/Xwt)
        base_rca = np.random.uniform(0.5, 2.0)  # Placeholder
        return base_rca
    
    def _calculate_sophistication(self, industry):
        """Calculate export sophistication index"""
        sophistication_map = {
            'manufacturing': 0.8,
            'technology': 0.9,
            'agriculture': 0.4,
            'mining': 0.3,
            'services': 0.6
        }
        
        category = self._categorize_industry(industry)
        return sophistication_map.get(category, 0.5)
    
    def _calculate_market_share(self, industry, destination, exports):
        """Calculate market share"""
        # Simplified market share (would need total market data)
        return min(exports / 10000000, 0.5)  # Cap at 50%
    
    def _calculate_import_penetration(self, industry, imports):
        """Calculate import penetration ratio"""
        # Simplified: imports / (domestic production + imports)
        # Using placeholder domestic production values
        domestic_production = imports * np.random.uniform(2, 10)
        return imports / (domestic_production + imports)
    
    def _assess_supply_chain_vulnerability(self, origin, industry):
        """Assess supply chain vulnerability"""
        # Risk factors: geographic concentration, political stability, etc.
        risk_countries = ['CN', 'RU', 'IR']  # Example high-risk countries
        base_risk = 0.3
        
        if origin in risk_countries:
            base_risk = 0.8
        
        # Industry-specific adjustments
        critical_industries = ['technology', 'pharmaceuticals', 'defense']
        if self._categorize_industry(industry) in critical_industries:
            base_risk *= 1.5
        
        return min(base_risk, 1.0)
    
    def _count_alternative_suppliers(self, industry, current_origin, all_imports_df):
        """Count alternative suppliers for this industry"""
        industry_imports = all_imports_df[all_imports_df['industry2'] == industry]
        alternative_origins = industry_imports['region1'].unique()
        
        # Exclude current origin
        alternatives = [origin for origin in alternative_origins if origin != current_origin]
        return len(alternatives)
    
    def _assess_strategic_importance(self, industry):
        """Assess strategic importance of industry"""
        strategic_industries = {
            'technology': 0.9,
            'pharmaceuticals': 0.9, 
            'defense': 1.0,
            'energy': 0.8,
            'agriculture': 0.7,
            'manufacturing': 0.6
        }
        
        category = self._categorize_industry(industry)
        return strategic_industries.get(category, 0.4)
    
    def create_state_reference_data(self, output_path):
        """Create state reference data files"""
        print("  📋 Creating state reference data...")
        output_path.mkdir(parents=True, exist_ok=True)

        # Save state codes
        self.state_codes.to_csv(output_path / 'state_codes.csv', index=False)
        
        # Save employment multipliers
        multipliers_df = pd.DataFrame([
            {'industry': industry, 'direct': mult['direct'], 
             'indirect': mult['indirect'], 'induced': mult['induced']}
            for industry, mult in self.employment_multipliers.items()
        ])
        multipliers_df.to_csv(output_path / 'employment_multipliers.csv', index=False)
        
        # Save state specializations
        specializations = []
        for state, industries in self.industry_state_mapping.items():
            for industry in industries:
                specializations.append({'state_code': state, 'specialization': industry})
        
        if specializations:
            spec_df = pd.DataFrame(specializations)
            spec_df.to_csv(output_path / 'state_specializations.csv', index=False)
        
        print("    ✅ Created state reference data files")