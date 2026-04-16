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
        print("    🗺️ Disaggregating domestic flows to state level...")

        CHUNK_SIZE = 100_000  # tune if needed
        chunks = []
        buffer = []

        for _, trade_row in base_trade_df.iterrows():
            state_disagg = self._disaggregate_single_flow(trade_row, bea_state_data)
            buffer.extend(state_disagg)

            # Flush to chunk when buffer gets large
            if len(buffer) >= CHUNK_SIZE:
                chunks.append(pd.DataFrame(buffer))
                buffer = []

        # Flush remaining
        if buffer:
            chunks.append(pd.DataFrame(buffer))

        if not chunks:
            return pd.DataFrame()

        # Concatenate efficiently
        state_df = pd.concat(chunks, ignore_index=True, copy=False)

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
        industry2_id = str(trade_row.get('industry2', ''))
        factor_entries = satellite.get(industry_id, []) if satellite else []

        trade_id = trade_row.get('trade_id', '')

        # First collect all candidate state-pair shares
        state_pairs = []
        for origin_state in producing_states:
            for dest_state in consuming_states:
                if origin_state == dest_state:
                    continue

                raw_share = self._calculate_state_flow_share(
                    origin_state, dest_state, industry, bea_data
                )

                if raw_share > 0:
                    state_pairs.append((origin_state, dest_state, raw_share))

        if not state_pairs:
            return flows

        total_share = sum(share for _, _, share in state_pairs)
        if total_share <= 0:
            return flows

        for origin_state, dest_state, raw_share in state_pairs:
            normalized_share = raw_share / total_share
            level = total_value * normalized_share

            interstate_id = (
                f"{self.year}-{trade_id}-US-{origin_state}-US-{dest_state}-{industry}"
            )

            if factor_entries:
                for fid, coeff in factor_entries:
                    flows.append({
                        'interstate_id': interstate_id,
                        'trade_id': trade_id,
                        'factor_id': fid,
                        'coefficient': coeff,
                        'state_industry_code': industry,
                        'level': level,
                        'flow_type': 'inter_state',
                        'employment_impact': 0,
                        '_origin_state': origin_state,
                        '_destination_state': dest_state,
                        '_industry1': industry_id,
                        '_industry2': industry2_id,
                    })
            else:
                flows.append({
                    'interstate_id': interstate_id,
                    'trade_id': trade_id,
                    'factor_id': -1,      
                    'coefficient': 1.0,   
                    'state_industry_code': industry,
                    'level': level,
                    'flow_type': 'inter_state',
                    'employment_impact': 0,
                    '_origin_state': origin_state,
                    '_destination_state': dest_state,
                    '_industry1': industry_id,
                    '_industry2': industry2_id,
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
        
        df = state_flows_df.copy()

        # Normalize amount column
        if 'amount' in df.columns and 'level' not in df.columns:
            df = df.rename(columns={'amount': 'level'})

        if 'level' not in df.columns:
            raise ValueError("state_flows_df must contain either 'level' or 'amount'")

        if 'employment_impact' not in df.columns:
            df['employment_impact'] = 0.0

        if 'economic_multiplier' not in df.columns:
            df['economic_multiplier'] = np.nan

        if 'tax_rate' not in df.columns:
            df['tax_rate'] = np.nan

        # Fill row-level fallback values
        df['economic_multiplier'] = df['economic_multiplier'].fillna(self.output_multiplier)
        df.loc[df['economic_multiplier'] <= 0, 'economic_multiplier'] = self.output_multiplier

        df['tax_rate'] = df['tax_rate'].fillna(self.tax_revenue_rate)
        df.loc[df['tax_rate'] < 0, 'tax_rate'] = self.tax_revenue_rate

        # Compute row-level impacts FIRST
        df['row_total_output_impact'] = df['level'] * df['economic_multiplier']
        df['row_tax_revenue_impact'] = df['row_total_output_impact'] * df['tax_rate']

        # Aggregate flows by destination state and industry
        state_industry_agg = df.groupby(
            ['_destination_state', 'state_industry_code'],
            as_index=False
        ).agg({
            'level': 'sum',
            'employment_impact': 'sum',
            'row_total_output_impact': 'sum',
            'row_tax_revenue_impact': 'sum'
        })
        
        impacts = []
        
        for _, row in state_industry_agg.iterrows():
            state = row['_destination_state']
            industry = row['state_industry_code']
            direct_jobs = float(row['employment_impact'])
            
            # Get multipliers
            multipliers = self.employment_multipliers.get(industry,
                                                        self.employment_multipliers['default'])
            
            # Calculate indirect and induced employment
            indirect_jobs = direct_jobs * multipliers['indirect']
            induced_jobs = direct_jobs * multipliers['induced']
            
            impacts.append({
                'region': f'US-{state}',
                'industry_code': industry,
                'direct_jobs': direct_jobs,
                'indirect_jobs': indirect_jobs, 
                'induced_jobs': induced_jobs,
                'total_output_impact': float(row['row_total_output_impact']),
                'tax_revenue_impact': float(row['row_tax_revenue_impact'])
            })
        
        impacts_df = pd.DataFrame(impacts)
        print(f"      ✅ Calculated impacts for {len(impacts_df)} state-industry combinations")
        
        return impacts_df
    
    def analyze_export_competitiveness(self, interstate_df):
        """
        State-level export competitiveness from interstate.csv.

        interstate_df columns: interstate_id, region1 (origin state), region2 (destination state),
                               industry1, amount (M EUR)

        Metrics per interstate_id:
          state_industry_exports_total : M EUR sent by this state+industry to all destination states
          state_destination_share      : this row's amount / state+industry total (0–1)
          state_export_intensity       : state+industry total / all interstate exports (0–1)
          state_destination_count      : distinct destination states for this state+industry
          state_export_concentration   : HHI of destinations for this state+industry (0=dispersed, 1=one)
        """
        print("    📈 Analyzing state export competitiveness from interstate data...")

        if interstate_df.empty:
            return pd.DataFrame()

        total = interstate_df['amount'].sum()

        def _hhi(amounts):
            t = amounts.sum()
            if t == 0:
                return 0.0
            s = amounts / t
            return round(float((s ** 2).sum()), 6)

        state_industry_stats = interstate_df.groupby(['region1', 'industry1']).agg(
            state_industry_exports_total=('amount', 'sum'),
            state_destination_count=('region2', 'nunique'),
        )
        state_industry_hhi = (
            interstate_df.groupby(['region1', 'industry1'])['amount']
            .apply(_hhi)
            .rename('state_export_concentration')
        )
        state_industry_stats = state_industry_stats.join(state_industry_hhi).reset_index()

        result = interstate_df[['interstate_id', 'region1', 'industry1', 'amount']].merge(
            state_industry_stats, on=['region1', 'industry1']
        )
        result['state_destination_share'] = (result['amount'] / result['state_industry_exports_total']).round(6)
        result['state_export_intensity'] = (result['state_industry_exports_total'] / total).round(6)
        result['state_industry_exports_total'] = result['state_industry_exports_total'].round(2)

        out = result[['interstate_id', 'state_industry_exports_total', 'state_destination_share',
                      'state_export_intensity', 'state_destination_count', 'state_export_concentration']]
        print(f"      ✅ State export competitiveness: {len(out)} rows, {interstate_df['region1'].nunique()} states")
        return out

    def analyze_import_dependency(self, interstate_df):
        """
        State-level import dependency from interstate.csv.

        Treats inbound interstate flows (region2 = destination state) as state imports.

        Metrics per interstate_id:
          state_industry_imports_total : M EUR received by this state+industry from all origin states
          state_source_share           : this row's amount / state+industry total (0–1)
          state_import_intensity       : state+industry total / all interstate imports (0–1)
          state_supplier_count         : distinct origin states supplying this state+industry
          state_import_concentration   : HHI of origins (higher = more dependent on fewer states)
        """
        print("    🔗 Analyzing state import dependency from interstate data...")

        if interstate_df.empty:
            return pd.DataFrame()

        total = interstate_df['amount'].sum()

        def _hhi(amounts):
            t = amounts.sum()
            if t == 0:
                return 0.0
            s = amounts / t
            return round(float((s ** 2).sum()), 6)

        state_industry_stats = interstate_df.groupby(['region2', 'industry1']).agg(
            state_industry_imports_total=('amount', 'sum'),
            state_supplier_count=('region1', 'nunique'),
        )
        state_industry_hhi = (
            interstate_df.groupby(['region2', 'industry1'])['amount']
            .apply(_hhi)
            .rename('state_import_concentration')
        )
        state_industry_stats = state_industry_stats.join(state_industry_hhi).reset_index()

        result = interstate_df[['interstate_id', 'region2', 'industry1', 'amount']].merge(
            state_industry_stats, on=['region2', 'industry1']
        )
        result['state_source_share'] = (result['amount'] / result['state_industry_imports_total']).round(6)
        result['state_import_intensity'] = (result['state_industry_imports_total'] / total).round(6)
        result['state_industry_imports_total'] = result['state_industry_imports_total'].round(2)

        out = result[['interstate_id', 'state_industry_imports_total', 'state_source_share',
                      'state_import_intensity', 'state_supplier_count', 'state_import_concentration']]
        print(f"      ✅ State import dependency: {len(out)} rows, {interstate_df['region2'].nunique()} states")
        return out
    
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