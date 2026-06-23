#!/usr/bin/env python
"""Basic test for the NLP step in the pipeline"""
from src.pipeline import OilSpillPipeline

# construct pipeline and populate minimal attributes
pipeline = OilSpillPipeline()
# fake coordinates and metadata (required by step_7)
pipeline.coordinates = {'lat_min': 0.0, 'lat_max': 0.0, 'lon_min': 0.0, 'lon_max': 0.0}
pipeline.metadata = {'DateTime': '2020-01-01 00:00:00'}
pipeline.cv_result = {'detected': True}

# use the provided csv in data/raw if present, else expect error
csv_path = 'data/raw/incidents_balanced_cleaned.csv'
try:
    out = pipeline.step_7_nlp_classification(csv_path=csv_path)
    print("NLP step output keys:", out.keys())
    assert 'classification' in out and 'confidence' in out
except FileNotFoundError:
    print("NLP CSV file not found; skipping test")

print("test_nlp completed")
