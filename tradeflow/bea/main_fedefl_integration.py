"""
FEDEFL Integration Module

Integrates Federal LCA Commons Elementary Flow List (FEDEFL) data
to provide comprehensive flow metadata and environmental impact details.
"""

import pandas as pd
import requests
import json
from pathlib import Path
import uuid

class FEDEFLIntegrator:
    def __init__(self):
        self.fedefl_base_url = "https://fedelemflowlist.github.io/fedelemflowlist"
        self.flows_cache = None
        self.contexts_cache = None
        
        # Common flow categories for trade analysis
        self.priority_contexts = [
            'emission/air',
            'emission/water',
            'emission/soil',
            'resource/air',
            'resource/water', 
            'resource/biotic',
            'resource/fossil fuel',
            'resource/land',
            'waste'
        ]
    
    def load_fedefl_flows(self):
        """Load FEDEFL flows from online source or create local version"""
        print("  🌿 Loading FEDEFL flow data...")
        
        try:
            # Try to load from FEDEFL online source
            flows_df = self._fetch_fedefl_online()
            if not flows_df.empty:
                print(f"    ✅ Loaded {len(flows_df)} FEDEFL flows from online source")
                self.flows_cache = flows_df
                return flows_df
                
        except Exception as e:
            print(f"    ⚠️ Online FEDEFL unavailable: {e}")
        
        # Fallback to local flow creation
        flows_df = self._create_local_flows()
        print(f"    ✅ Created {len(flows_df)} local environmental flows")
        self.flows_cache = flows_df
        return flows_df
    
    def _fetch_fedefl_online(self):
        """Fetch FEDEFL data from online source"""
        # FEDEFL API endpoints (hypothetical - adjust to actual API)
        flows_url = f"{self.fedefl_base_url}/flows.json"
        contexts_url = f"{self.fedefl_base_url}/contexts.json"
        
        # Fetch flows
        flows_response = requests.get(flows_url, timeout=10)
        flows_response.raise_for_status()
        flows_data = flows_response.json()
        
        # Fetch contexts
        contexts_response = requests.get(contexts_url, timeout=10)
        contexts_response.raise_for_status()
        contexts_data = contexts_response.json()
        
        # Process into DataFrame
        flows_df = self._process_fedefl_data(flows_data, contexts_data)
        return flows_df
    
    def _process_fedefl_data(self, flows_data, contexts_data):
        """Process raw FEDEFL data into standardized DataFrame"""
        flows = []
        
        for flow in flows_data:
            flow_record = {
                'flow_uuid': flow.get('uuid', str(uuid.uuid4())),
                'flowable': flow.get('flowable', ''),
                'context': flow.get('context', ''),
                'unit': flow.get('unit', ''),
                'compartment': self._extract_compartment(flow.get('context', '')),
                'flow_class': flow.get('class', 'environmental'),
                'preferred': flow.get('preferred', True),
                'external_reference': flow.get('external_reference', ''),
                'cas_number': flow.get('cas_number', ''),
                'formula': flow.get('formula', ''),
                'synonyms': '; '.join(flow.get('synonyms', []))
            }
            flows.append(flow_record)
        
        return pd.DataFrame(flows)
    
    def _create_local_flows(self):
        """Create local environmental flows based on common trade impacts"""
        flows = []
        
        # Air emissions
        air_emissions = [
            ('Carbon dioxide', 'kg', 'b6f010fb-a764-3063-af2d-bcb8309a97b7'),
            ('Methane', 'kg', '7b8b7b8b-a764-3063-af2d-bcb8309a97b8'),
            ('Nitrous oxide', 'kg', '8c9c8c9c-a764-3063-af2d-bcb8309a97b9'),
            ('Sulfur dioxide', 'kg', '9d0d9d0d-a764-3063-af2d-bcb8309a97c0'),
            ('Nitrogen oxides', 'kg', 'a1e1a1e1-a764-3063-af2d-bcb8309a97c1'),
            ('Particulate matter', 'kg', 'b2f2b2f2-a764-3063-af2d-bcb8309a97c2'),
            ('Carbon monoxide', 'kg', 'c3g3c3g3-a764-3063-af2d-bcb8309a97c3'),
            ('Volatile organic compounds', 'kg', 'd4h4d4h4-a764-3063-af2d-bcb8309a97c4'),
            ('Ammonia', 'kg', 'e5i5e5i5-a764-3063-af2d-bcb8309a97c5'),
            ('Benzene', 'kg', 'f6j6f6j6-a764-3063-af2d-bcb8309a97c6')
        ]
        
        for flowable, unit, uuid_str in air_emissions:
            flows.append({
                'flow_uuid': uuid_str,
                'flowable': flowable,
                'context': 'emission/air',
                'unit': unit,
                'compartment': 'air',
                'flow_class': 'environmental',
                'preferred': True,
                'external_reference': 'EPA',
                'cas_number': '',
                'formula': '',
                'synonyms': ''
            })
        
        # Water emissions
        water_emissions = [
            ('Biological oxygen demand', 'kg', '10a10a10-a764-3063-af2d-bcb8309a97c7'),
            ('Chemical oxygen demand', 'kg', '11b11b11-a764-3063-af2d-bcb8309a97c8'),
            ('Suspended solids', 'kg', '12c12c12-a764-3063-af2d-bcb8309a97c9'),
            ('Nitrogen total', 'kg', '13d13d13-a764-3063-af2d-bcb8309a97d0'),
            ('Phosphorus total', 'kg', '14e14e14-a764-3063-af2d-bcb8309a97d1'),
            ('Heavy metals', 'kg', '15f15f15-a764-3063-af2d-bcb8309a97d2')
        ]
        
        for flowable, unit, uuid_str in water_emissions:
            flows.append({
                'flow_uuid': uuid_str,
                'flowable': flowable,
                'context': 'emission/water',
                'unit': unit,
                'compartment': 'water',
                'flow_class': 'environmental',
                'preferred': True,
                'external_reference': 'EPA',
                'cas_number': '',
                'formula': '',
                'synonyms': ''
            })
        
        # Resource use
        resources = [
            ('Water use', 'L', '16g16g16-a764-3063-af2d-bcb8309a97d3'),
            ('Energy use', 'MJ', '17h17h17-a764-3063-af2d-bcb8309a97d4'),
            ('Land use', 'm2', '18i18i18-a764-3063-af2d-bcb8309a97d5'),
            ('Fossil fuel depletion', 'MJ surplus', '19j19j19-a764-3063-af2d-bcb8309a97d6'),
            ('Mineral depletion', 'kg Fe equiv', '20k20k20-a764-3063-af2d-bcb8309a97d7')
        ]
        
        for flowable, unit, uuid_str in resources:
            flows.append({
                'flow_uuid': uuid_str,
                'flowable': flowable,
                'context': 'resource/natural',
                'unit': unit,
                'compartment': 'natural resources',
                'flow_class': 'resource',
                'preferred': True,
                'external_reference': 'EPA',
                'cas_number': '',
                'formula': '',
                'synonyms': ''
            })
        
        # Employment and economic flows
        economic_flows = [
            ('Employment', 'person*year', '21l21l21-a764-3063-af2d-bcb8309a97d8'),
            ('Value added', 'USD', '22m22m22-a764-3063-af2d-bcb8309a97d9'),
            ('Tax revenue', 'USD', '23n23n23-a764-3063-af2d-bcb8309a97e0')
        ]
        
        for flowable, unit, uuid_str in economic_flows:
            flows.append({
                'flow_uuid': uuid_str,
                'flowable': flowable,
                'context': 'economic',
                'unit': unit,
                'compartment': 'economic',
                'flow_class': 'economic',
                'preferred': True,
                'external_reference': 'BEA',
                'cas_number': '',
                'formula': '',
                'synonyms': ''
            })
        
        return pd.DataFrame(flows)
    
    def _extract_compartment(self, context):
        """Extract compartment from context string"""
        if '/' in context:
            return context.split('/')[1]
        return context
    
    def map_factors_to_flows(self, factors_df):
        """Map trade factors to FEDEFL flows"""
        print("  🔗 Mapping trade factors to FEDEFL flows...")
        
        if self.flows_cache is None:
            self.load_fedefl_flows()
        
        mapped_factors = []
        
        for _, factor in factors_df.iterrows():
            factor_name = factor.get('factor_name', factor.iloc[0] if len(factor) > 0 else '')
            
            # Try to find matching flow
            matching_flow = self._find_matching_flow(factor_name)
            
            if matching_flow is not None:
                mapped_factors.append({
                    'factor_id': factor.get('factor_id', factor.name),
                    'factor_name': factor_name,
                    'flow_uuid': matching_flow['flow_uuid'],
                    'flowable': matching_flow['flowable'],
                    'context': matching_flow['context'],
                    'unit': matching_flow['unit'],
                    'match_quality': 'high' if factor_name.lower() == matching_flow['flowable'].lower() else 'medium'
                })
            else:
                # Create new flow for unmapped factors
                new_flow = self._create_flow_for_factor(factor_name)
                mapped_factors.append({
                    'factor_id': factor.get('factor_id', factor.name),
                    'factor_name': factor_name,
                    'flow_uuid': new_flow['flow_uuid'],
                    'flowable': new_flow['flowable'],
                    'context': new_flow['context'],
                    'unit': new_flow['unit'],
                    'match_quality': 'created'
                })
        
        mapping_df = pd.DataFrame(mapped_factors)
        print(f"    ✅ Mapped {len(mapping_df)} factors to flows")
        
        return mapping_df
    
    def _find_matching_flow(self, factor_name):
        """Find matching FEDEFL flow for a factor"""
        if self.flows_cache is None or factor_name is None:
            return None
        
        factor_lower = str(factor_name).lower()
        
        # Exact match first
        exact_matches = self.flows_cache[
            self.flows_cache['flowable'].str.lower() == factor_lower
        ]
        
        if not exact_matches.empty:
            return exact_matches.iloc[0].to_dict()
        
        # Partial match
        partial_matches = self.flows_cache[
            self.flows_cache['flowable'].str.lower().str.contains(factor_lower, na=False)
        ]
        
        if not partial_matches.empty:
            return partial_matches.iloc[0].to_dict()
        
        # Keyword matching for common cases
        keywords = {
            'co2': 'carbon dioxide',
            'ch4': 'methane', 
            'n2o': 'nitrous oxide',
            'so2': 'sulfur dioxide',
            'nox': 'nitrogen oxides',
            'pm': 'particulate matter',
            'water': 'water use',
            'energy': 'energy use',
            'land': 'land use'
        }
        
        for keyword, flowable in keywords.items():
            if keyword in factor_lower:
                keyword_matches = self.flows_cache[
                    self.flows_cache['flowable'].str.lower().str.contains(flowable, na=False)
                ]
                if not keyword_matches.empty:
                    return keyword_matches.iloc[0].to_dict()
        
        return None
    
    def _create_flow_for_factor(self, factor_name):
        """Create new flow for unmapped factor"""
        # Determine likely context based on factor name
        factor_lower = str(factor_name).lower()
        
        if any(word in factor_lower for word in ['emission', 'co2', 'ch4', 'pollut']):
            context = 'emission/air'
            compartment = 'air'
            unit = 'kg'
        elif any(word in factor_lower for word in ['water', 'aquatic']):
            context = 'emission/water'
            compartment = 'water'
            unit = 'kg'
        elif any(word in factor_lower for word in ['employ', 'job', 'worker']):
            context = 'economic'
            compartment = 'economic'
            unit = 'person*year'
        elif any(word in factor_lower for word in ['energy', 'mj', 'kwh']):
            context = 'resource/energy'
            compartment = 'energy'
            unit = 'MJ'
        else:
            context = 'environmental'
            compartment = 'environmental'
            unit = 'kg'
        
        new_flow = {
            'flow_uuid': str(uuid.uuid4()),
            'flowable': factor_name,
            'context': context,
            'unit': unit,
            'compartment': compartment,
            'flow_class': 'environmental',
            'preferred': True,
            'external_reference': 'Generated',
            'cas_number': '',
            'formula': '',
            'synonyms': ''
        }
        
        # Add to cache
        if self.flows_cache is not None:
            new_flow_df = pd.DataFrame([new_flow])
            self.flows_cache = pd.concat([self.flows_cache, new_flow_df], ignore_index=True)
        
        return new_flow
    
    def create_comprehensive_flow_table(self, output_path):
        """Create comprehensive flow.csv table"""
        print("  📊 Creating comprehensive flow table...")
        
        if self.flows_cache is None:
            self.load_fedefl_flows()
        
        # Enhance flows with additional metadata
        enhanced_flows = self.flows_cache.copy()
        
        # Add trade relevance scoring
        enhanced_flows['trade_relevance'] = enhanced_flows.apply(
            self._calculate_trade_relevance, axis=1
        )
        
        # Sort by relevance and preferred status
        enhanced_flows = enhanced_flows.sort_values([
            'trade_relevance', 'preferred', 'flowable'
        ], ascending=[False, False, True])
        
        # Save comprehensive flow table
        output_file = output_path / 'flow.csv'
        enhanced_flows.to_csv(output_file, index=False)
        
        print(f"    ✅ Created comprehensive flow table with {len(enhanced_flows)} flows")
        
        # Create summary statistics
        self._create_flow_summary(enhanced_flows, output_path)
        
        return enhanced_flows
    
    def _calculate_trade_relevance(self, flow_row):
        """Calculate relevance score for trade analysis"""
        flowable = str(flow_row['flowable']).lower()
        context = str(flow_row['context']).lower()
        
        # High relevance flows
        high_relevance_terms = [
            'carbon dioxide', 'co2', 'methane', 'ch4', 'employment', 
            'energy', 'water', 'land use', 'gdp', 'value added'
        ]
        
        # Medium relevance flows
        medium_relevance_terms = [
            'nitrogen', 'sulfur', 'particulate', 'pollution', 
            'waste', 'resource', 'mineral', 'fossil'
        ]
        
        score = 0
        
        # Check flowable name
        for term in high_relevance_terms:
            if term in flowable:
                score += 10
                break
        else:
            for term in medium_relevance_terms:
                if term in flowable:
                    score += 5
                    break
        
        # Context bonuses
        if 'emission' in context:
            score += 3
        elif 'resource' in context:
            score += 2
        elif 'economic' in context:
            score += 8
        
        # Preferred flows get bonus
        if flow_row.get('preferred', False):
            score += 2
        
        return score
    
    def _create_flow_summary(self, flows_df, output_path):
        """Create flow summary statistics"""
        summary_stats = {
            'total_flows': len(flows_df),
            'by_context': flows_df['context'].value_counts().to_dict(),
            'by_compartment': flows_df['compartment'].value_counts().to_dict(),
            'by_flow_class': flows_df['flow_class'].value_counts().to_dict(),
            'high_relevance_flows': len(flows_df[flows_df['trade_relevance'] >= 10]),
            'preferred_flows': len(flows_df[flows_df['preferred'] == True])
        }
        
        # Save summary as JSON
        with open(output_path / 'flow_summary.json', 'w') as f:
            json.dump(summary_stats, f, indent=2)
        
        print(f"    📋 Flow summary: {summary_stats['total_flows']} total, "
              f"{summary_stats['high_relevance_flows']} high-relevance flows")
    
    def validate_flow_completeness(self, trade_factors_df, output_path):
        """Validate that all trade factors have corresponding flows"""
        print("  ✅ Validating flow completeness...")
        
        if trade_factors_df.empty:
            print("    ⚠️ No trade factors to validate")
            return
        
        # Map factors to flows
        mapping = self.map_factors_to_flows(trade_factors_df)
        
        # Check for missing mappings
        unmapped = mapping[mapping['match_quality'] == 'created']
        
        validation_report = {
            'total_factors': len(trade_factors_df),
            'mapped_factors': len(mapping),
            'exact_matches': len(mapping[mapping['match_quality'] == 'high']),
            'partial_matches': len(mapping[mapping['match_quality'] == 'medium']),
            'created_flows': len(unmapped),
            'unmapped_factors': unmapped['factor_name'].tolist() if not unmapped.empty else []
        }
        
        # Save validation report
        with open(output_path / 'flow_validation.json', 'w') as f:
            json.dump(validation_report, f, indent=2)
        
        print(f"    ✅ Validation complete: {validation_report['mapped_factors']}/{validation_report['total_factors']} factors mapped")