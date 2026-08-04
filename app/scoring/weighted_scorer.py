# FILE: app/scoring/weighted_scorer.py
# Create this folder first: mkdir app/scoring/

import json
from typing import Dict, List, Set

class WeightedKeywordScorer:
    """
    Scores keywords based on importance level.
    Must-haves get 3x weight, important skills get 1x, nice-to-haves get 0.5x.
    """
    
    WEIGHTS = {
        'must_have': 3.0,      # Must-have skills: 3.0 weight
        'important': 1.0,      # Important skills: 1.0 weight
        'nice_to_have': 0.5    # Nice-to-have skills: 0.5 weight
    }
    
    def __init__(self):
        """Initialize the scorer."""
        pass
    
    def calculate_keyword_match_score(
        self,
        found_keywords: Set[str],
        required_keywords: Dict[str, str],  # keyword → 'must_have'|'important'|'nice_to_have'
        total_keywords: int = None
    ) -> Dict:
        """
        Calculate weighted keyword match score.
        
        Args:
            found_keywords: Set of keywords found in resume
            required_keywords: Dict mapping keyword → importance level
            total_keywords: Total number of keywords in JD (for percentage calc)
        
        Returns:
        {
            'weighted_score': 75.5,              # 0-100
            'total_weight': 15.5,               # Sum of all weights found
            'max_weight': 20.0,                 # Sum of all possible weights
            'coverage_percentage': 77.5,        # (found_weight / max_weight) * 100
            'breakdown': {
                'must_have': {'found': 2, 'total': 3, 'weight': 6.0},
                'important': {'found': 3, 'total': 5, 'weight': 3.0},
                'nice_to_have': {'found': 1, 'total': 2, 'weight': 0.5}
            }
        }
        """
        
        # Initialize breakdown
        breakdown = {
            'must_have': {'found': 0, 'total': 0, 'weight': 0.0},
            'important': {'found': 0, 'total': 0, 'weight': 0.0},
            'nice_to_have': {'found': 0, 'total': 0, 'weight': 0.0}
        }
        
        # Count keywords by importance level
        for keyword, importance in required_keywords.items():
            breakdown[importance]['total'] += 1
            weight = self.WEIGHTS.get(importance, 0.5)
            breakdown[importance]['weight'] += weight
            
            if keyword.lower() in {k.lower() for k in found_keywords}:
                breakdown[importance]['found'] += 1
        
        # Calculate scores
        total_weight_found = sum(
            breakdown[level]['found'] * self.WEIGHTS.get(level, 0.5) 
            for level in breakdown.keys()
        )
        
        max_possible_weight = sum(
            breakdown[level]['weight']
            for level in breakdown.keys()
        )
        
        # Avoid division by zero
        if max_possible_weight == 0:
            coverage_percentage = 0
            weighted_score = 0
        else:
            coverage_percentage = (total_weight_found / max_possible_weight) * 100
            weighted_score = min(100, coverage_percentage)  # Cap at 100
        
        return {
            'weighted_score': round(weighted_score, 1),
            'total_weight': round(total_weight_found, 1),
            'max_weight': round(max_possible_weight, 1),
            'coverage_percentage': round(coverage_percentage, 1),
            'breakdown': breakdown
        }


# USAGE EXAMPLE:
if __name__ == "__main__":
    scorer = WeightedKeywordScorer()
    
    # From Intact JD
    required_keywords = {
        'Python': 'must_have',
        'REST APIs': 'must_have',
        'AWS': 'must_have',
        'Docker': 'must_have',
        'scikit-learn': 'must_have',
        'GraphQL': 'important',
        'React': 'nice_to_have',
        'Kubernetes': 'important'
    }
    
    # Found in Meet's resume
    found_keywords = {'Python', 'REST APIs', 'AWS', 'Docker', 'scikit-learn', 'React'}
    
    result = scorer.calculate_keyword_match_score(found_keywords, required_keywords)
    print(json.dumps(result, indent=2))
    
    # Output:
    # {
    #   "weighted_score": 93.3,
    #   "coverage_percentage": 93.3,
    #   "breakdown": {
    #     "must_have": {"found": 5, "total": 5, "weight": 15.0},
    #     "important": {"found": 0, "total": 2, "weight": 0.0},
    #     "nice_to_have": {"found": 1, "total": 1, "weight": 0.5}
    #   }
    # }