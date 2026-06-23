"""
Random Forest Oil Spill Classifier (AI-Based)
Notebook 5: RF Classifier
"""

import os
import json
import pickle
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from scipy import stats

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import joblib

try:
    from scipy import ndimage
    import cv2
except ImportError:
    ndimage = None
    cv2 = None

logger = logging.getLogger(__name__)


def extract_comprehensive_features(sar_image: np.ndarray, binary_mask: np.ndarray) -> Dict[str, float]:
    """
    Extract comprehensive set of features from SAR image and mask for RF classification
    
    Parameters:
    -----------
    sar_image : np.ndarray
        SAR image in dB
    binary_mask : np.ndarray
        Binary mask of detected region
    
    Returns:
    --------
    dict
        Comprehensive feature dictionary with 15+ features
    """
    features = {}
    
    # 1. Statistical features from backscatter
    sar_masked = sar_image[binary_mask > 0]
    sar_background = sar_image[binary_mask == 0]
    
    if len(sar_masked) > 0:
        features['backscatter_mean'] = float(np.mean(sar_masked))
        features['backscatter_std'] = float(np.std(sar_masked))
        features['backscatter_skewness'] = float(stats.skew(sar_masked))
        features['backscatter_kurtosis'] = float(stats.kurtosis(sar_masked))
        features['backscatter_min'] = float(np.min(sar_masked))
        features['backscatter_max'] = float(np.max(sar_masked))
    else:
        features['backscatter_mean'] = -20.0
        features['backscatter_std'] = 0.0
        features['backscatter_skewness'] = 0.0
        features['backscatter_kurtosis'] = 0.0
        features['backscatter_min'] = -20.0
        features['backscatter_max'] = -20.0
    
    if len(sar_background) > 0:
        features['background_mean'] = float(np.mean(sar_background))
        features['contrast_ratio'] = features['background_mean'] - features['backscatter_mean']
    else:
        features['background_mean'] = -10.0
        features['contrast_ratio'] = 10.0
    
    # 2. Texture features (GLCM-based statistics)
    texture_feats = extract_texture_features(sar_image, binary_mask)
    features.update(texture_feats)
    
    # 3. Geometric features (shape and size)
    geom_feats = extract_geometric_features_rf(binary_mask)
    features.update(geom_feats)
    
    # 4. Morphological features
    if ndimage:
        try:
            labeled, num_features = ndimage.label(binary_mask)
            if num_features > 0:
                sizes = ndimage.sum(binary_mask, labeled, range(num_features + 1))
                largest_size = np.max(sizes)
                features['num_components'] = float(num_features)
                features['largest_component_ratio'] = float(largest_size / np.sum(binary_mask)) if np.sum(binary_mask) > 0 else 0.0
            else:
                features['num_components'] = 0.0
                features['largest_component_ratio'] = 0.0
        except Exception as e:
            logger.warning(f"Could not compute morphological features: {e}")
            features['num_components'] = 0.0
            features['largest_component_ratio'] = 0.0
    
    return features


def extract_texture_features(sar_image: np.ndarray, binary_mask: np.ndarray) -> Dict[str, float]:
    """
    Extract texture features from SAR region using statistical methods (GLCM-like)
    
    Parameters:
    -----------
    sar_image : np.ndarray
        SAR image in dB
    binary_mask : np.ndarray
        Binary mask of region
    
    Returns:
    --------
    dict
        Texture features: contrast, homogeneity, energy, correlation
    """
    sar_masked = sar_image[binary_mask > 0]
    
    if len(sar_masked) == 0:
        return {
            'texture_contrast': 0.0,
            'texture_homogeneity': 0.0,
            'texture_energy': 0.0,
            'texture_correlation': 0.0
        }
    
    # Normalize image to 0-1 range for texture calculation
    sar_norm = (sar_masked - np.min(sar_masked)) / (np.max(sar_masked) - np.min(sar_masked) + 1e-6)
    
    # Convert to integer levels for GLCM calculation (16 levels)
    levels = 16
    sar_levels = np.floor(sar_norm * (levels - 1)).astype(int)
    
    # Compute GLCM-like statistics
    features = {
        'texture_contrast': 0.0,
        'texture_homogeneity': 0.0,
        'texture_energy': 0.0,
        'texture_correlation': 0.0
    }
    
    try:
        # Simplified GLCM: use pixel value differences and co-occurrence statistics
        if len(sar_levels) > 1:
            diff = np.diff(sar_norm)  # Pixel differences
            
            # Contrast: measure of local variations
            features['texture_contrast'] = float(np.mean(np.abs(diff)))
            
            # Energy: sum of squared GLCM elements (indicates uniform intensity)
            hist, _ = np.histogram(sar_norm, bins=16, range=(0, 1))
            features['texture_energy'] = float(np.sum(hist ** 2) / (len(sar_norm) ** 2))
            
            # Homogeneity: closeness of GLCM distribution to diagonal
            features['texture_homogeneity'] = float(1.0 - features['texture_contrast'])
            
            # Correlation: statistical relationship between pixels
            features['texture_correlation'] = float(np.corrcoef(sar_norm[:-1], sar_norm[1:])[0, 1]) if len(sar_norm) > 1 else 0.0
    except Exception as e:
        logger.warning(f"Texture feature calculation failed: {e}")
        features = {
            'texture_contrast': 0.1,
            'texture_homogeneity': 0.9,
            'texture_energy': 0.5,
            'texture_correlation': 0.0
        }
    
    return features



def extract_geometric_features_rf(binary_mask: np.ndarray) -> Dict[str, float]:
    """
    Extract geometric features from binary mask
    
    Parameters:
    -----------
    binary_mask : np.ndarray
        Binary mask of oil spill region
    
    Returns:
    --------
    dict
        Geometric features
    """
    if cv2 is None:
        logger.warning("OpenCV not available, using fallback geometric features")
        return {'elongation_ratio': 1.0, 'compactness': 1.0, 'area_pixels': 0.0}
    
    features = {}
    
    # Find contours
    contours, _ = cv2.findContours(binary_mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return {'elongation_ratio': 1.0, 'compactness': 1.0, 'area_pixels': 0.0}
    
    # Get largest contour
    contour = max(contours, key=cv2.contourArea)
    
    # Calculate properties
    area = cv2.contourArea(contour)
    perimeter = cv2.arcLength(contour, True)
    
    features['area_pixels'] = float(area)
    
    # Fit ellipse if possible
    if len(contour) >= 5:
        try:
            ellipse = cv2.fitEllipse(contour)
            (cx, cy), (major_axis, minor_axis), orientation = ellipse
            
            elongation_ratio = major_axis / (minor_axis + 1e-6)
            compactness = (4 * np.pi * area) / (perimeter ** 2 + 1e-6)
            
            features['elongation_ratio'] = float(elongation_ratio)
            features['compactness'] = float(compactness)
        except Exception:
            features['elongation_ratio'] = 1.0
            features['compactness'] = 1.0
    else:
        features['elongation_ratio'] = 1.0
        features['compactness'] = 1.0
    
    return features


def extract_radiometric_features_rf(sar_image: np.ndarray, binary_mask: np.ndarray) -> Dict[str, float]:
    """
    Extract radiometric features from SAR image
    
    Parameters:
    -----------
    sar_image : np.ndarray
        SAR image in dB
    binary_mask : np.ndarray
        Binary mask
    
    Returns:
    --------
    dict
        Radiometric features
    """
    sar_masked = sar_image[binary_mask > 0]
    
    if len(sar_masked) == 0:
        return {'mean_intensity': 0.0, 'std_intensity': 0.0}
    
    features = {
        'mean_intensity': float(np.mean(sar_masked)),
        'std_intensity': float(np.std(sar_masked))
    }
    
    return features


def extract_oil_detection_features(sar_image: np.ndarray, binary_mask: np.ndarray) -> Dict[str, float]:
    """
    Extract all relevant features for RF classification using comprehensive feature set
    
    Parameters:
    -----------
    sar_image : np.ndarray
        SAR image in dB
    binary_mask : np.ndarray
        Binary mask of detected region
    
    Returns:
    --------
    dict
        All features needed for RF prediction (15+ features)
    """
    # Use the comprehensive feature extraction function
    features = extract_comprehensive_features(sar_image, binary_mask)
    
    return features



class RFClassifier:
    """Random Forest Classifier for oil spill detection"""
    
    def __init__(self, model_path: str = None):
        """
        Initialize RF classifier
        
        Parameters:
        -----------
        model_path : str, optional
            Path to pre-trained model
        """
        self.model = None
        # Comprehensive feature list matching extract_comprehensive_features output
        self.feature_names = [
            # Statistical features
            'backscatter_mean',
            'backscatter_std',
            'backscatter_skewness',
            'backscatter_kurtosis',
            'backscatter_min',
            'backscatter_max',
            'background_mean',
            'contrast_ratio',
            # Texture features (GLCM)
            'texture_contrast',
            'texture_homogeneity',
            'texture_energy',
            'texture_correlation',
            # Geometric features
            'area_pixels',
            'perimeter',
            'elongation_ratio',
            'compactness',
            # Morphological features
            'num_components',
            'largest_component_ratio'
        ]
        
        if model_path and os.path.exists(model_path):
            self.load_model(model_path)
    
    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        n_estimators: int = 50,
        max_depth: int = 10,
        random_state: int = 42
    ) -> Dict:
        """
        Train Random Forest classifier
        
        Parameters:
        -----------
        X_train : pd.DataFrame
            Training features
        y_train : pd.Series
            Training labels (0=non-oil, 1=oil)
        n_estimators : int
            Number of trees
        max_depth : int
            Maximum tree depth
        random_state : int
            Random seed
        
        Returns:
        --------
        dict
            Training results
        """
        logger.info("Training Random Forest classifier...")
        
        self.model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_split=2,
            random_state=random_state
        )
        
        self.model.fit(X_train, y_train)
        
        # Evaluate on training data
        y_pred = self.model.predict(X_train)
        accuracy = accuracy_score(y_train, y_pred)
        
        logger.info(f"Training accuracy: {accuracy:.4f}")
        
        # Get feature importances
        importances = self.model.feature_importances_
        feature_importance = {
            name: float(imp) 
            for name, imp in zip(self.feature_names, importances)
        }
        
        result = {
            'training_accuracy': float(accuracy),
            'feature_importances': feature_importance,
            'model_params': {
                'n_estimators': n_estimators,
                'max_depth': max_depth,
                'random_state': random_state
            }
        }
        
        logger.info(f"Feature importances: {feature_importance}")
        
        return result
    
    def predict(self, X: pd.DataFrame, return_proba: bool = False) -> Dict:
        """
        Make predictions on new data
        
        Parameters:
        -----------
        X : pd.DataFrame
            Features with columns: mean_intensity, std_intensity, 
                                   elongation_ratio, compactness
        return_proba : bool
            Return prediction probabilities
        
        Returns:
        --------
        dict
            Predictions with labels and optionally probabilities
        """
        if self.model is None:
            raise RuntimeError("Model not trained. Call train() first or load_model()")
        
        predictions = self.model.predict(X)
        
        result = {
            'predictions': [int(p) for p in predictions],
            'labels': ['Non-oil' if p == 0 else 'Oil-like' for p in predictions]
        }
        
        if return_proba:
            probabilities = self.model.predict_proba(X)
            result['probabilities'] = {
                'non_oil': probabilities[:, 0].tolist(),
                'oil_like': probabilities[:, 1].tolist()
            }
            result['confidence'] = np.max(probabilities, axis=1).tolist()
        
        return result
    
    def predict_single(self, features: Dict, return_proba: bool = True) -> Dict:
        """
        Predict on single sample
        
        Parameters:
        -----------
        features : dict
            Features dictionary with keys:
            - mean_intensity
            - std_intensity
            - elongation_ratio
            - compactness
        return_proba : bool
            Return prediction probability
        
        Returns:
        --------
        dict
            Prediction result
        """
        # Create DataFrame from single sample
        X = pd.DataFrame([features])
        X = X[self.feature_names]  # Ensure correct column order
        
        prediction = self.model.predict(X)[0]
        label = 'Non-oil' if prediction == 0 else 'Oil-like'
        
        result = {
            'prediction': int(prediction),
            'label': label
        }
        
        if return_proba:
            proba = self.model.predict_proba(X)[0]
            result['confidence_non_oil'] = float(proba[0])
            result['confidence_oil_like'] = float(proba[1])
            result['confidence'] = float(max(proba))
        
        return result
    
    def predict_from_image(self, sar_image: np.ndarray, binary_mask: np.ndarray) -> Dict:
        """
        Predict oil spill directly from SAR image and mask using trained model.
        
        Raises RuntimeError if model is not loaded.
        
        Parameters:
        -----------
        sar_image : np.ndarray
            SAR image in dB
        binary_mask : np.ndarray
            Binary mask of detected region
        
        Returns:
        --------
        dict
            Prediction result with features, confidence, and feature importance
            
        Raises:
        -------
        RuntimeError
            If trained model is not available
        """
        if self.model is None:
            raise RuntimeError(
                "RF model not trained/loaded. Cannot make predictions. "
                "Train the model first using rf_classifier.train() or load a pre-trained "
                "model file using rf_classifier.load_model(path/to/model.pkl)"
            )
        
        # Extract features from image and mask
        features = extract_oil_detection_features(sar_image, binary_mask)
        
        num_features = len(features)
        logger.info(f"Extracted {num_features} RF features")
        logger.info(f"Feature values: {features}")
        
        # Make prediction
        result = self.predict_single(features, return_proba=True)
        result['features'] = features
        result['model_available'] = True
        result['num_features'] = num_features
        
        # Get feature importance from the model
        try:
            import pandas as pd
            feature_importance = dict(zip(self.feature_names, self.model.feature_importances_))
            # Sort by importance and get top 3
            top_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:3]
            result['top_features'] = top_features
            
            # Log top features
            top_feature_names = [f[0] for f in top_features]
            logger.info(f"Top features: {', '.join(top_feature_names)}")
        except Exception as e:
            logger.debug(f"Could not extract feature importance: {e}")
            result['top_features'] = []
        
        return result
    
    def evaluate(
        self,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        verbose: bool = True
    ) -> Dict:
        """
        Evaluate classifier on test data
        
        Parameters:
        -----------
        X_test : pd.DataFrame
            Test features
        y_test : pd.Series
            Test labels
        verbose : bool
            Print detailed report
        
        Returns:
        --------
        dict
            Evaluation results
        """
        if self.model is None:
            raise RuntimeError("Model not trained")
        
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        
        cm = confusion_matrix(y_test, y_pred)
        
        result = {
            'accuracy': float(accuracy),
            'confusion_matrix': {
                'true_negatives': int(cm[0, 0]),
                'false_positives': int(cm[0, 1]),
                'false_negatives': int(cm[1, 0]),
                'true_positives': int(cm[1, 1])
            }
        }
        
        if verbose:
            logger.info(f"Test accuracy: {accuracy:.4f}")
            logger.info(f"Confusion matrix:\n{cm}")
            logger.info(classification_report(y_test, y_pred, target_names=['Non-oil', 'Oil-like']))
        
        return result
    
    def save_model(self, output_path: str) -> None:
        """Save trained model to disk"""
        if self.model is None:
            raise RuntimeError("No model to save")
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        joblib.dump(self.model, output_path)
        logger.info(f"Model saved to {output_path}")
    
    def load_model(self, model_path: str) -> None:
        """Load trained model from disk"""
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found: {model_path}")
        
        self.model = joblib.load(model_path)
        logger.info(f"Model loaded from {model_path}")


def generate_synthetic_data(n_samples_per_class: int = 15) -> pd.DataFrame:
    """
    Generate synthetic SAR data for training
    
    Parameters:
    -----------
    n_samples_per_class : int
        Samples per class
    
    Returns:
    --------
    pd.DataFrame
        Synthetic data with features and labels
    """
    np.random.seed(42)
    data = []
    
    # Oil-like samples (label=1)
    for _ in range(n_samples_per_class):
        data.append({
            'mean_intensity': np.random.uniform(-16.5, -14),
            'std_intensity': np.random.uniform(0.1, 1.3),
            'elongation_ratio': np.random.uniform(1.5, 3.0),
            'compactness': np.random.uniform(1.8, 2.8),
            'label': 1
        })
    
    # Non-oil samples (label=0)
    for _ in range(n_samples_per_class):
        data.append({
            'mean_intensity': np.random.uniform(-13, -11),
            'std_intensity': np.random.uniform(1.0, 2.2),
            'elongation_ratio': np.random.uniform(0.8, 1.4),
            'compactness': np.random.uniform(0.9, 1.7),
            'label': 0
        })
    
    return pd.DataFrame(data).sample(frac=1, random_state=42).reset_index(drop=True)


def load_training_data(csv_path: str) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Load training data from CSV
    
    Parameters:
    -----------
    csv_path : str
        Path to CSV file with training data
    
    Returns:
    --------
    tuple
        (features, labels)
    """
    df = pd.read_csv(csv_path)
    X = df[['mean_intensity', 'std_intensity', 'elongation_ratio', 'compactness']]
    y = df['label']
    return X, y
