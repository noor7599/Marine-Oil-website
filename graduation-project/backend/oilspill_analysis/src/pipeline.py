"""
Main Pipeline Orchestrator
Automates the complete oil spill analysis workflow from SAR image to final decision
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Optional
from pathlib import Path

# Import all modules
from config import Config, get_config, set_config
from cv_model import run_cv_inference, extract_oil_pixels
from coordinate_extractor import process_sar_image
from data_downloader import download_environmental_data
from simulator import run_simulation
from pg_classifier import classify_with_physical_guidance, ClassifierConfig as PGConfig
from rf_classifier import RFClassifier, generate_synthetic_data, load_training_data
from decision_layer import make_ensemble_decision
from report_generator import generate_comprehensive_report

logger = logging.getLogger(__name__)


class OilSpillPipeline:
    """Complete oil spill detection pipeline"""
    
    def __init__(self, config_path: str = None):
        """
        Initialize pipeline with configuration
        
        Parameters:
        -----------
        config_path : str, optional
            Path to configuration JSON file
        """
        self.config = Config(config_path)
        set_config(self.config)
        
        # Setup logging
        self._setup_logging()
        
        # Initialize classifiers
        self.rf_classifier = None
        self.cv_result = None
        self.pg_result = None
        self.rf_result = None
        
        logger.info("Oil Spill Pipeline initialized")
    
    def _setup_logging(self):
        """Setup logging to file and console"""
        log_dir = self.config.get('data.logs_dir')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f'pipeline_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        
        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)
    
    def step_0_cv_inference(self, image_path: str = None) -> Dict:
        """
        Step 0: Computer Vision Model - MariNeXt Oil Spill Detection
        
        Parameters:
        -----------
        image_path : str, optional
            Path to SAR TIFF image
        
        Returns:
        --------
        dict
            CV inference results with mask and visualization paths
        """
        logger.info("=" * 60)
        logger.info("STEP 0: Computer Vision Model Inference")
        logger.info("=" * 60)
        
        if image_path is None:
            # Auto-detect image
            from .coordinate_extractor import auto_detect_image
            image_path = auto_detect_image()
        
        if not os.path.exists(image_path):
            logger.warning(f"Image not found: {image_path}")
            return {'status': 'error', 'message': 'Image not found'}
        
        output_dir = self.config.get('data.outputs_dir')
        result = run_cv_inference(image_path, output_dir=output_dir)
        
        if result.get('status') == 'success':
            self.cv_result = result
            self.cv_mask_path = result.get('mask_path')
            logger.info(f"CV Detection: Mask saved to {self.cv_mask_path}")
        else:
            logger.warning(f"CV inference skipped: {result.get('error', 'Unknown error')}")
        
        return result
    
    def step_1_extract_coordinates(self, image_path: str = None) -> Dict:
        """
        Step 1: Extract coordinates from SAR image
        
        Parameters:
        -----------
        image_path : str, optional
            Path to SAR TIFF image (auto-detect if not provided)
        
        Returns:
        --------
        dict
            Extracted coordinates and metadata
        """
        logger.info("=" * 60)
        logger.info("STEP 1: Extract Coordinates from SAR Image")
        logger.info("=" * 60)
        
        output_dir = self.config.get('data.processed_dir')
        result = process_sar_image(image_path, output_dir)
        
        # Save results
        self.image_path = result['image_path']
        self.coordinates = result['coordinates']
        self.metadata = result['metadata']
        
        logger.info(f"Coordinates extracted: {self.coordinates}")
        
        return result
    
    def step_2_download_data(self, metadata_file: str = None) -> Dict:
        """
        Step 2: Download ERA5 and CMEMS data
        
        Parameters:
        -----------
        metadata_file : str, optional
            Path to metadata JSON from step 1
        
        Returns:
        --------
        dict
            Downloaded data file paths and verification
        """
        logger.info("=" * 60)
        logger.info("STEP 2: Download Environmental Data")
        logger.info("=" * 60)
        
        if metadata_file is None:
            # Find latest metadata file
            processed_dir = self.config.get('data.processed_dir')
            metadata_files = [f for f in os.listdir(processed_dir) if f.endswith('.metadata.json')]
            if not metadata_files:
                raise FileNotFoundError("No metadata file found. Run step 1 first.")
            metadata_file = os.path.join(processed_dir, sorted(metadata_files)[-1])
        
        output_dir = self.config.get('data.processed_dir')
        result = download_environmental_data(metadata_file, output_dir)
        
        # Save reference
        self.era5_file = result['files']['era5']
        self.cmems_file = result['files']['cmems']
        self.download_date = result['date']
        
        logger.info(f"Downloaded ERA5: {self.era5_file}")
        logger.info(f"Downloaded CMEMS: {self.cmems_file}")
        
        return result
    
    def step_3_run_simulation(self) -> Dict:
        """
        Step 3: Run oil spill simulation
        
        Returns:
        --------
        dict
            Simulation results and output file path
        """
        logger.info("=" * 60)
        logger.info("STEP 3: Run Oil Spill Simulation")
        logger.info("=" * 60)
        
        if not hasattr(self, 'coordinates') or not hasattr(self, 'era5_file'):
            raise RuntimeError("Must run steps 1-2 first")
        
        release_lat = (self.coordinates['lat_min'] + self.coordinates['lat_max']) / 2
        release_lon = (self.coordinates['lon_min'] + self.coordinates['lon_max']) / 2
        
        from datetime import datetime
        release_time = datetime.fromisoformat(self.download_date).replace(hour=12, minute=0, second=0)
        
        output_dir = self.config.get('data.outputs_dir')
        
        result = run_simulation(
            self.era5_file,
            self.cmems_file,
            release_lat,
            release_lon,
            release_time,
            output_dir,
            num_particles=self.config.get('simulation.num_particles'),
            duration_hours=self.config.get('simulation.duration_hours')
        )
        
        self.simulation_file = result['results']['outfile']
        
        logger.info(f"Simulation output: {self.simulation_file}")
        
        return result
    
    def step_4_pg_classification(
        self,
        sar_image_path: str = None,
        binary_mask_path: str = None
    ) -> Dict:
        """
        Step 4: Physics-Guided classification
        
        Parameters:
        -----------
        sar_image_path : str, optional
            Path to SAR image
        binary_mask_path : str, optional
            Path to binary mask of detected region
        
        Returns:
        --------
        dict
            Physics-guided classification result
        """
        logger.info("=" * 60)
        logger.info("STEP 4: Physics-Guided Classification")
        logger.info("=" * 60)
        
        if not hasattr(self, 'simulation_file'):
            raise RuntimeError("Must run step 3 first")
        
        # Auto-detect SAR image if not provided
        if sar_image_path is None:
            from .coordinate_extractor import auto_detect_image
            sar_image_path = auto_detect_image()
            if sar_image_path:
                logger.info(f"Auto-detected SAR image: {sar_image_path}")
        
        # Use CV mask if available
        if binary_mask_path is None and hasattr(self, 'cv_mask_path'):
            binary_mask_path = self.cv_mask_path
            logger.info("Using mask from CV model (Step 0)")
        
        if sar_image_path is None or binary_mask_path is None:
            logger.warning("SAR image or mask not provided; skipping PG classification")
            return {'classification': 'Not performed', 'confidence': 0.5}
        
        import numpy as np
        import rasterio
        
        # Load SAR image
        with rasterio.open(sar_image_path) as src:
            sar_image = src.read(1)
        
        # Load binary mask
        binary_mask = np.load(binary_mask_path)
        
        # Get spot centroid
        spot_lat = (self.coordinates['lat_min'] + self.coordinates['lat_max']) / 2
        spot_lon = (self.coordinates['lon_min'] + self.coordinates['lon_max']) / 2
        
        config = PGConfig()
        result = classify_with_physical_guidance(
            sar_image,
            binary_mask,
            self.simulation_file,
            (spot_lat, spot_lon),
            config
        )
        
        self.pg_result = result
        
        logger.info(f"PG Classification: {result['classification']} (confidence: {result['confidence']:.2f})")
        
        return result
    
    def step_5_rf_classification(self, features: Dict = None) -> Dict:
        """
        Step 5: Random Forest classification
        
        Parameters:
        -----------
        features : dict, optional
            Feature dictionary with keys:
            - mean_intensity
            - std_intensity
            - elongation_ratio
            - compactness
        
        Returns:
        --------
        dict
            Random Forest classification result
        """
        logger.info("=" * 60)
        logger.info("STEP 5: Random Forest Classification")
        logger.info("=" * 60)
        
        if self.rf_classifier is None:
            logger.warning("RF classifier not trained; training on synthetic data")
            # Generate and train on synthetic data
            synthetic_data = generate_synthetic_data()
            from sklearn.model_selection import train_test_split
            X = synthetic_data[['mean_intensity', 'std_intensity', 'elongation_ratio', 'compactness']]
            y = synthetic_data['label']
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            
            self.rf_classifier = RFClassifier()
            self.rf_classifier.train(X_train, y_train)
        
        if features is None:
            logger.warning("No features provided for RF classification")
            return {'label': 'Non-oil', 'confidence': 0.5}
        
        result = self.rf_classifier.predict_single(features, return_proba=True)
        
        self.rf_result = result
        
        logger.info(f"RF Classification: {result['label']} (confidence: {result['confidence']:.2f})")
        
        return result
    
    def step_6_decision_layer(self, nlp_result: Optional[Dict] = None) -> Dict:
        """
        Step 6: Ensemble decision layer
        
        Parameters:
        -----------
        nlp_result : dict, optional
            NLP classification result
        
        Returns:
        --------
        dict
            Final ensemble decision
        """
        logger.info("=" * 60)
        logger.info("STEP 6: Ensemble Decision Layer")
        logger.info("=" * 60)
        
        # Use available results, or provide defaults
        pg_result = getattr(self, 'pg_result', {'classification': 'Not performed', 'confidence': 0.5})
        rf_result = getattr(self, 'rf_result', {'classification': 'Not performed', 'confidence': 0.5})
        
        weights = {
            'cv': self.config.get('decision_layer.cv_weight'),
            'pg': self.config.get('decision_layer.pg_weight'),
            'rf': self.config.get('decision_layer.rf_weight'),
            'nlp': self.config.get('decision_layer.nlp_weight')
        }
        
        # include CV confidence if present
        cv_score = None
        if self.cv_result and self.cv_result.get('confidence') is not None:
            try:
                cv_score = float(self.cv_result.get('confidence', 0))
            except Exception:
                cv_score = None
        
        final_decision = make_ensemble_decision(
            pg_result,
            rf_result,
            nlp_result,
            cv_score=cv_score,
            weights=weights
        )
        
        logger.info(f"Final Decision: {final_decision['final_prediction']} "
                   f"(confidence: {final_decision['final_confidence']:.2f})")
        
        return final_decision

    def step_7_nlp_classification(self, csv_path: str = None) -> Dict:
        """
        Step 7: Run NLP validation/classification using historical incident data.
        This method wraps :func:`~src.model.validate_detection` and converts the
        output into the simple ``{'classification':..., 'confidence':...}``
        format expected by the decision layer.

        The detector uses the centroid of the SAR image coordinates and the
        acquisition timestamp extracted in ``step_1_extract_coordinates``.  If
        the pipeline has not yet executed step 1 an exception is raised.

        Parameters
        ----------
        csv_path : str, optional
            Path to the CSV file containing incident records.  If not provided
            the default file in ``data/raw`` is used.
        """
        logger.info("=" * 60)
        logger.info("STEP 7: NLP Validation/Classification")
        logger.info("=" * 60)

        if not hasattr(self, 'coordinates') or not hasattr(self, 'metadata'):
            raise RuntimeError("Coordinates and metadata are required for NLP step")

        # compute centroid
        lat = (self.coordinates['lat_min'] + self.coordinates['lat_max']) / 2
        lon = (self.coordinates['lon_min'] + self.coordinates['lon_max']) / 2

        # try to get a timestamp from metadata
        timestamp = self.metadata.get('DateTime') or self.metadata.get('TIFFTAG_DATETIME')
        if timestamp is None:
            from datetime import datetime
            timestamp = datetime.now().isoformat()

        from .model import validate_detection

        # default csv path located under raw data directory
        if csv_path is None:
            raw_dir = self.config.get('data.raw_dir') or os.path.join('data', 'raw')
            csv_path = os.path.join(raw_dir, 'incidents_balanced_cleaned.csv')

        result = validate_detection(
            csv_path,
            lat,
            lon,
            timestamp,
            is_oil_prediction=self.cv_result.get('detected', False),
            xlsx_path=None,
            generate_pdf=False
        )

        oil_pct = result['summary'].get('oil_match_percentage', 0)
        classification = 'Oil-like' if oil_pct >= 50 else 'Non-oil'
        confidence = min(max(oil_pct / 100.0, 0.0), 1.0)

        nlp_output = {
            'classification': classification,
            'confidence': confidence,
            'details': result
        }
        self.nlp_result = nlp_output
        logger.info(f"NLP classification: {classification} (confidence: {confidence:.2f})")
        return nlp_output
    
    def run_complete_pipeline(
        self,
        image_path: str = None,
        sar_image_path: str = None,
        binary_mask_path: str = None,
        features: Dict = None,
        nlp_result: Dict = None
    ) -> Dict:
        """
        Run complete pipeline from image to final decision
        
        Parameters:
        -----------
        image_path : str, optional
            SAR TIFF image path (auto-detect if not provided)
        sar_image_path : str, optional
            Path to SAR image for PG classification
        binary_mask_path : str, optional
            Path to binary mask for PG classification
        features : dict, optional
            Features for RF classification
        nlp_result : dict, optional
            NLP classification result
        
        Returns:
        --------
        dict
            Complete pipeline results
        """
        logger.info("\n" + "=" * 60)
        logger.info("STARTING COMPLETE OIL SPILL ANALYSIS PIPELINE")
        logger.info("=" * 60 + "\n")
        
        try:
            # Step 0: CV Model Inference
            step0_result = self.step_0_cv_inference(image_path)
            
            # CHECK: Did CV model detect oil?
            if not step0_result.get('detected', False):
                logger.warning("=" * 60)
                logger.warning("NO OIL DETECTED IN CV MODEL STEP")
                logger.warning("Skipping further analysis and proceeding to final decision")
                logger.warning("=" * 60)
                
                # Create empty results for skipped steps
                pipeline_results = {
                    'timestamp': datetime.now().isoformat(),
                    'step_0_cv_inference': step0_result,
                    'step_1_extract_coordinates': {'status': 'skipped', 'reason': 'No oil detected'},
                    'step_2_download_data': {'status': 'skipped', 'reason': 'No oil detected'},
                    'step_3_run_simulation': {'status': 'skipped', 'reason': 'No oil detected'},
                    'step_4_pg_classification': {'classification': 'No oil', 'confidence': 1.0},
                    'step_5_rf_classification': {'classification': 'No oil', 'confidence': 1.0},
                    'step_6_nlp_classification': {'classification': 'No oil', 'confidence': 1.0},
                    'step_7_final_decision': {
                        'final_classification': 'NO OIL DETECTED',
                        'confidence': 1.0,
                        'method': 'CV Model detected 0% oil pixels'
                    }
                }
                
                # Save pipeline results
                output_dir = self.config.get('data.outputs_dir')
                results_file = os.path.join(
                    output_dir,
                    f'pipeline_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
                )
                with open(results_file, 'w') as f:
                    json.dump(pipeline_results, f, indent=2, default=str)
                
                logger.info(f"\n[OK] Pipeline complete! Results saved to {results_file}")
                logger.info(f"Final Decision: {pipeline_results['step_6_final_decision']['final_classification']}")
                
                # Generate comprehensive HTML report
                try:
                    report_files = generate_comprehensive_report(
                        pipeline_results=pipeline_results,
                        output_dir=output_dir
                    )
                    if report_files and 'comprehensive_html' in report_files:
                        logger.info(f"✓ Comprehensive HTML report generated: {report_files['comprehensive_html']}")
                except Exception as e:
                    logger.warning(f"Report generation failed (non-critical): {e}")
                
                return pipeline_results
            
            # Oil was detected - continue with full analysis
            logger.info(f"Oil detected: {step0_result.get('oil_percentage', 0):.2f}% - Continuing with full analysis")
            
            # Step 1: Extract coordinates
            step1_result = self.step_1_extract_coordinates(image_path)
            
            # Step 2: Download data
            step2_result = self.step_2_download_data()
            
            # Step 3: Run simulation
            step3_result = self.step_3_run_simulation()
            
            # Step 4: PG classification
            step4_result = self.step_4_pg_classification(sar_image_path, binary_mask_path)
            
            # Step 5: RF classification
            step5_result = self.step_5_rf_classification(features)

            # Step 6: NLP classification (automatically run if not supplied)
            nlp_step_output = nlp_result
            if nlp_step_output is None:
                try:
                    nlp_step_output = self.step_7_nlp_classification()
                except Exception as exc:  # noqa: F841
                    logger.warning(f"NLP step failed or skipped: {exc}")
                    nlp_step_output = {'classification': 'Not available', 'confidence': 0.0}

            # Step 7: Ensemble decision using all available models
            step7_result = self.step_6_decision_layer(nlp_step_output)

            # Compile all results
            pipeline_results = {
                'timestamp': datetime.now().isoformat(),
                'step_0_cv_inference': step0_result,
                'step_1_extract_coordinates': step1_result,
                'step_2_download_data': step2_result,
                'step_3_run_simulation': step3_result,
                'step_4_pg_classification': step4_result,
                'step_5_rf_classification': step5_result,
                'step_6_nlp_classification': nlp_step_output,
                'step_7_final_decision': step7_result
            }
            
            # Save pipeline results
            output_dir = self.config.get('data.outputs_dir')
            results_file = os.path.join(
                output_dir,
                f'pipeline_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            )
            with open(results_file, 'w') as f:
                json.dump(pipeline_results, f, indent=2, default=str)
            
            logger.info(f"\n[OK] Pipeline complete! Results saved to {results_file}")
            
            # Generate comprehensive HTML report
            try:
                report_files = generate_comprehensive_report(
                    pipeline_results=pipeline_results,
                    output_dir=output_dir
                )
                if report_files and 'comprehensive_html' in report_files:
                    logger.info(f"✓ Comprehensive HTML report generated: {report_files['comprehensive_html']}")
            except Exception as e:
                logger.warning(f"Report generation failed (non-critical): {e}")
            
            return pipeline_results
            
        except Exception as e:
            logger.error(f"\n[FAILED] Pipeline failed: {str(e)}")
            raise
    
    def save_config(self, output_path: str) -> None:
        """Save current configuration"""
        self.config.save(output_path)
        logger.info(f"Configuration saved to {output_path}")


def run_pipeline(config_path: str = None, **pipeline_args) -> Dict:
    """
    Convenience function to run complete pipeline
    
    Parameters:
    -----------
    config_path : str, optional
        Path to configuration file
    **pipeline_args : dict
        Arguments to pass to run_complete_pipeline()
    
    Returns:
    --------
    dict
        Pipeline results
    """
    pipeline = OilSpillPipeline(config_path)
    return pipeline.run_complete_pipeline(**pipeline_args)
