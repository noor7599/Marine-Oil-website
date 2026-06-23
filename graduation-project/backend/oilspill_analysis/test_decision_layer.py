#!/usr/bin/env python
"""Unit tests for decision_layer module"""

from src.decision_layer import DecisionLayer, make_ensemble_decision


def test_default_weights():
    dl = DecisionLayer()
    # default weights defined in constructor should sum to 1
    total = dl.cv_weight + dl.pg_weight + dl.rf_weight + dl.nlp_weight
    assert abs(total - 1.0) < 1e-6
    assert abs(dl.cv_weight - 0.3) < 1e-6
    assert abs(dl.pg_weight - 0.3) < 1e-6
    assert abs(dl.rf_weight - 0.1) < 1e-6
    assert abs(dl.nlp_weight - 0.3) < 1e-6


def test_make_ensemble_with_cv():
    pg = {'classification': 'Oil-like', 'confidence': 0.5}
    rf = {'label': 'Oil-like', 'confidence': 0.5}

    result = make_ensemble_decision(pg, rf, cv_score=0.8)
    assert isinstance(result, dict)
    assert 'final_confidence' in result
    assert result['final_prediction'] in ['Oil-like', 'Non-oil']
    # ensure cv score influenced the decision summary presence
    assert 'individual_decisions' in result
    names = [d['model_name'] for d in result['individual_decisions']]
    assert 'CV Detection' in names
