"""
Main entry point for Oil Spill Analysis Pipeline
Run this script to execute the complete automated workflow
"""

import sys
import argparse
import logging
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.pipeline import run_pipeline, OilSpillPipeline

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Oil Spill Analysis Pipeline - Automated Workflow'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        help='Path to configuration JSON file'
    )
    
    parser.add_argument(
        '--image',
        type=str,
        help='Path to SAR TIFF image (auto-detect if not provided)'
    )
    
    parser.add_argument(
        '--sar-image',
        type=str,
        help='Path to SAR image for PG classification'
    )
    
    parser.add_argument(
        '--mask',
        type=str,
        help='Path to binary mask for PG classification'
    )
    
    parser.add_argument(
        '--step',
        type=int,
        choices=[0, 1, 2, 3, 4, 5, 6, 7],
        help='Run specific pipeline step (0-7; 7 = NLP validation)'
    )

    parser.add_argument(
        '--csv',
        type=str,
        help='Path to incident CSV file (used by NLP step)'
    )
    
    parser.add_argument(
        '--save-config',
        type=str,
        help='Save default configuration to file'
    )
    
    args = parser.parse_args()
    
    # Initialize pipeline
    try:
        pipeline = OilSpillPipeline(args.config)
        
        # Handle config saving
        if args.save_config:
            pipeline.save_config(args.save_config)
            logger.info(f"Configuration saved to {args.save_config}")
            return
        
        # Run specific step or complete pipeline
        if args.step:
            logger.info(f"Running pipeline step {args.step}...")
            
            if args.step == 0:
                result = pipeline.step_0_cv_inference(args.image)
            elif args.step == 1:
                result = pipeline.step_1_extract_coordinates(args.image)
            elif args.step == 2:
                result = pipeline.step_2_download_data()
            elif args.step == 3:
                result = pipeline.step_3_run_simulation()
            elif args.step == 4:
                result = pipeline.step_4_pg_classification(args.sar_image, args.mask)
            elif args.step == 5:
                result = pipeline.step_5_rf_classification()
            elif args.step == 6:
                result = pipeline.step_6_decision_layer()
            elif args.step == 7:
                result = pipeline.step_7_nlp_classification(csv_path=args.csv)
            
            logger.info(f"Step {args.step} completed successfully")
        else:
            # Run complete pipeline
            logger.info("Running complete pipeline...")
            result = pipeline.run_complete_pipeline(
                image_path=args.image,
                sar_image_path=args.sar_image,
                binary_mask_path=args.mask
            )
        
        logger.info("[OK] Pipeline execution completed")
        
    except Exception as e:
        logger.error(f"[FAILED] Pipeline failed: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
