"""
LLM-Powered Feature Engineering

Uses Claude AI to analyze prediction errors and suggest new features
based on error patterns and business context.
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Any, Optional
import json

logger = logging.getLogger(__name__)


class LLMFeatureEngineer:
    """
    Uses Claude AI to suggest features based on error analysis
    """

    def __init__(self, anthropic_api_key: Optional[str] = None):
        """
        Initialize LLM feature engineer

        Args:
            anthropic_api_key: Anthropic API key (optional, reads from env if not provided)
        """
        self.api_key = anthropic_api_key
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=anthropic_api_key) if anthropic_api_key else None
        except ImportError:
            logger.warning("Anthropic package not installed. LLM features will be skipped.")
            self.client = None

    def analyze_errors(
        self,
        train_df: pd.DataFrame,
        test_df: pd.DataFrame,
        predictions: np.ndarray,
        current_features: List[str],
        restaurant_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze prediction errors and identify patterns

        Args:
            train_df: Training data
            test_df: Test data
            predictions: Model predictions on test data
            current_features: List of current feature names
            restaurant_context: Business context (type, location, etc.)

        Returns:
            Dictionary with error analysis and LLM suggestions
        """
        # Calculate errors
        errors_df = test_df.copy()
        errors_df['pred'] = predictions
        errors_df['error'] = errors_df['y'] - errors_df['pred']
        errors_df['error_pct'] = np.abs(errors_df['error'] / (errors_df['y'] + 1)) * 100
        errors_df['over_under'] = np.where(errors_df['error'] > 0, 'under', 'over')

        # Find worst predictions
        worst_days = errors_df.nlargest(5, 'error_pct')

        # Analyze error patterns
        error_patterns = {
            'avg_error_pct': errors_df['error_pct'].mean(),
            'worst_days': worst_days[['ds', 'y', 'pred', 'error_pct', 'day_of_week', 'is_weekend']].to_dict('records'),
            'error_by_day_of_week': errors_df.groupby('day_of_week')['error_pct'].mean().to_dict(),
            'over_predictions': (errors_df['over_under'] == 'over').sum(),
            'under_predictions': (errors_df['over_under'] == 'under').sum(),
        }

        # Get LLM suggestions if client available
        if self.client:
            llm_suggestions = self._get_llm_suggestions(
                error_patterns,
                current_features,
                restaurant_context
            )
        else:
            logger.warning("LLM client not available. Using rule-based suggestions.")
            llm_suggestions = self._get_rule_based_suggestions(error_patterns, current_features)

        return {
            'error_patterns': error_patterns,
            'llm_suggestions': llm_suggestions
        }

    def _get_llm_suggestions(
        self,
        error_patterns: Dict[str, Any],
        current_features: List[str],
        restaurant_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get feature suggestions from Claude AI

        Args:
            error_patterns: Analyzed error patterns
            current_features: Current features
            restaurant_context: Restaurant business context

        Returns:
            LLM suggestions dictionary
        """
        # Build prompt
        prompt = self._build_prompt(error_patterns, current_features, restaurant_context)

        try:
            # Call Claude API
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Parse response
            suggestions = self._parse_llm_response(response.content[0].text)

            logger.info(f"✓ LLM suggested {len(suggestions['features'])} new features")
            return suggestions

        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            return self._get_rule_based_suggestions(error_patterns, current_features)

    def _build_prompt(
        self,
        error_patterns: Dict[str, Any],
        current_features: List[str],
        restaurant_context: Dict[str, Any]
    ) -> str:
        """Build prompt for Claude AI"""

        worst_days_str = "\n".join([
            f"  - {day['ds'].strftime('%Y-%m-%d')} ({['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][day['day_of_week']]}): "
            f"Predicted {day['pred']:.0f}, Actual {day['y']:.0f}, Error {day['error_pct']:.1f}%"
            for day in error_patterns['worst_days']
        ])

        error_by_dow_str = "\n".join([
            f"  - {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][dow]}: {error:.1f}% avg error"
            for dow, error in sorted(error_patterns['error_by_day_of_week'].items())
        ])

        prompt = f"""I'm training a demand forecasting model for a restaurant.

**Restaurant Context:**
- Type: {restaurant_context.get('type', 'Cloud Kitchen')}
- Area: {restaurant_context.get('area_type', 'Residential')}
- Location: {restaurant_context.get('location', 'Gurugram, India')}
- Primary Channel: {restaurant_context.get('primary_channel', 'Delivery (Swiggy/Zomato)')}
- Walk-in %: {restaurant_context.get('walk_in_pct', 20)}%

**Current Model Performance:**
- Average Test Error: {error_patterns['avg_error_pct']:.1f}%
- Over-predictions: {error_patterns['over_predictions']}
- Under-predictions: {error_patterns['under_predictions']}

**Worst Prediction Days:**
{worst_days_str}

**Error by Day of Week:**
{error_by_dow_str}

**Current Features ({len(current_features)}):**
{', '.join(current_features[:15])}...

**Task:**
Suggest 5-8 NEW features that could capture the error patterns above.

**Requirements:**
1. Features must be GENERIC (work for any cloud kitchen, not just this one)
2. Based on calendar patterns, business context, or behavioral patterns
3. Should address the specific error patterns shown above
4. Implementable with available data (date, day of week, basic temporal info)

**Format your response as JSON:**
{{
  "features": [
    {{
      "name": "feature_name",
      "description": "What it captures",
      "rationale": "Why it helps with the errors above",
      "implementation": "How to calculate it"
    }}
  ],
  "expected_impact": "Estimated MAPE improvement"
}}"""

        return prompt

    def _parse_llm_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse Claude AI response

        Args:
            response_text: Raw response from Claude

        Returns:
            Parsed suggestions dictionary
        """
        try:
            # Try to extract JSON from response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1

            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                suggestions = json.loads(json_str)
                return suggestions
            else:
                raise ValueError("No JSON found in response")

        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")

            # Fallback: extract feature names from text
            features = []
            lines = response_text.split('\n')
            for line in lines:
                if 'name' in line.lower() or 'feature' in line.lower():
                    # Simple extraction
                    if ':' in line:
                        parts = line.split(':')
                        if len(parts) >= 2:
                            feature_name = parts[1].strip().strip('"').strip(',')
                            if feature_name and len(feature_name) < 50:
                                features.append({
                                    'name': feature_name,
                                    'description': 'LLM suggested feature',
                                    'rationale': 'Extracted from LLM response',
                                    'implementation': 'Manual implementation needed'
                                })

            return {
                'features': features[:5],  # Limit to 5
                'expected_impact': 'Unknown',
                'raw_response': response_text
            }

    def _get_rule_based_suggestions(
        self,
        error_patterns: Dict[str, Any],
        current_features: List[str]
    ) -> Dict[str, Any]:
        """
        Fallback: Rule-based feature suggestions

        Args:
            error_patterns: Error analysis
            current_features: Current features

        Returns:
            Rule-based suggestions
        """
        suggestions = {
            'features': [],
            'expected_impact': '5-10% MAPE reduction (rule-based estimate)'
        }

        # Suggest features based on error patterns
        if error_patterns['error_by_day_of_week'].get(4, 0) > error_patterns['avg_error_pct'] * 1.2:
            # Friday errors high
            suggestions['features'].append({
                'name': 'is_pre_weekend_surge',
                'description': 'Captures Friday evening surge pattern',
                'rationale': 'Friday errors are higher than average',
                'implementation': '(day_of_week == 4).astype(int)'
            })

        if error_patterns['error_by_day_of_week'].get(6, 0) > error_patterns['avg_error_pct'] * 1.2:
            # Sunday errors high
            suggestions['features'].append({
                'name': 'is_sunday_evening_pattern',
                'description': 'Sunday dinner orders differ from other days',
                'rationale': 'Sunday errors are higher than average',
                'implementation': '(day_of_week == 6).astype(int)'
            })

        # Generic helpful features
        suggestions['features'].extend([
            {
                'name': 'days_since_month_start',
                'description': 'Spending patterns change through the month',
                'rationale': 'Payday effects (1st and 15th)',
                'implementation': 'day_of_month'
            },
            {
                'name': 'week_of_month',
                'description': 'Week 1 vs Week 4 spending differs',
                'rationale': 'Monthly spending cycle',
                'implementation': '(day_of_month - 1) // 7 + 1'
            }
        ])

        return suggestions


def implement_llm_feature(df: pd.DataFrame, feature_def: Dict[str, Any]) -> pd.DataFrame:
    """
    Implement a feature suggested by LLM

    Args:
        df: DataFrame to add feature to
        feature_def: Feature definition from LLM

    Returns:
        DataFrame with new feature
    """
    feature_name = feature_def['name']
    implementation = feature_def.get('implementation', '')

    try:
        # Try to evaluate the implementation string
        # CAUTION: Only do this with trusted LLM output
        if 'day_of_week' in implementation and 'day_of_week' in df.columns:
            df[feature_name] = eval(implementation.replace('day_of_week', 'df["day_of_week"]'))
        elif 'day_of_month' in implementation and 'day_of_month' in df.columns:
            df[feature_name] = eval(implementation.replace('day_of_month', 'df["day_of_month"]'))
        elif 'is_weekend' in implementation and 'is_weekend' in df.columns:
            df[feature_name] = eval(implementation.replace('is_weekend', 'df["is_weekend"]'))
        else:
            # Create placeholder
            df[feature_name] = 0
            logger.warning(f"Could not implement feature {feature_name}, using placeholder")

        logger.info(f"  ✓ Implemented feature: {feature_name}")

    except Exception as e:
        logger.error(f"Failed to implement feature {feature_name}: {e}")
        df[feature_name] = 0

    return df
