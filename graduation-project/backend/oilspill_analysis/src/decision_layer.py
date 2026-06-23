"""
Decision Layer - Weighted Ensemble of Model Outputs
Combines CV Detection, Physics-Guided Classifier, and NLP outputs with configurable weights
"""

import json
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ModelDecision:
    """Individual model decision"""
    model_name: str
    prediction: str  # "Oil" or "Non-Oil"
    confidence: float  # 0-1
    weight: float  # 0-1


@dataclass
class EnsembleDecision:
    """Final ensemble decision"""
    final_prediction: str  # "Oil" or "Non-Oil"
    final_confidence: float  # 0-1
    individual_decisions: List[ModelDecision]
    decision_summary: Dict


class DecisionLayer:
    """Weighted ensemble decision layer (CV + PG + NLP)"""
    
    def __init__(
        self,
        pg_weight: float = 0.35,
        nlp_weight: float = 0.20,
        cv_weight: float = 0.45,
        confidence_threshold: float = 0.40
    ):
        """
        Initialize decision layer
        
        Parameters:
        -----------
        pg_weight : float
            Weight for Physics-Guided classifier (0-1)
        nlp_weight : float
            Weight for NLP classifier (0-1)
        cv_weight : float
            Weight for CV Detection (0-1)
        confidence_threshold : float
            Confidence threshold for final decision (0-1)
        """
        # Normalize weights (CV, PG, NLP only - RF removed)
        total = pg_weight + nlp_weight + cv_weight
        self.pg_weight = pg_weight / total
        self.nlp_weight = nlp_weight / total
        self.cv_weight = cv_weight / total
        self.confidence_threshold = confidence_threshold
        
        logger.info(f"Decision weights - CV: {self.cv_weight:.2f}, PG: {self.pg_weight:.2f}, NLP: {self.nlp_weight:.2f}")
    
    def decide(
        self,
        pg_result: Dict,
        nlp_result: Optional[Dict] = None,
        cv_score: Optional[float] = None
    ) -> EnsembleDecision:
        """
        Make ensemble decision combining CV, Physics-Guided, and NLP models
        
        REFACTORED LOGIC (Fixed):
        Each model contributes evidence to ONE of two categories:
        - Oil_evidence (positive vote for "Oil")
        - NonOil_evidence (positive vote for "Non-Oil/False Positive")
        
        Final decision: if Oil_evidence > NonOil_evidence → "Oil Spill"
                      else → "False Positive"
        
        Parameters:
        -----------
        pg_result : dict
            Physics-Guided classifier result with keys:
            - 'classification': "Oil-like" or "False Positive"
            - 'confidence': 0-1
        nlp_result : dict, optional
            NLP classifier result with keys:
            - 'confidence': 0-1 (if available)
            - 'risk_level': "HIGH", "MEDIUM", "LOW", "VERY_LOW" (fallback)
        cv_score : float, optional
            CV detection confidence score (0-1)
        
        Returns:
        --------
        EnsembleDecision
            Final weighted ensemble decision
        """
        # Map risk_level to confidence for NLP if confidence is missing,
        # then down-weight by match quality and cap effective confidence.
        def _get_nlp_confidence(nlp_result):
            """Extract or compute effective NLP confidence from result"""
            if nlp_result is None:
                # NLP absent → neutral: no evidence either way
                return 0.0

            # Base confidence: explicit field if present, else from risk_level
            risk_map = {
                'HIGH': 0.90,
                'MEDIUM': 0.75,
                'LOW': 0.60,
                'VERY_LOW': 0.30
            }
            if 'confidence' in nlp_result:
                base_conf = float(nlp_result.get('confidence', 0.5))
            else:
                risk_level = nlp_result.get('risk_level', 'LOW')
                base_conf = risk_map.get(str(risk_level).upper(), 0.5)

            # Match-quality factor
            joint_matches = int(nlp_result.get('joint_matches', 0) or 0)
            time_matches = int(nlp_result.get('time_matches', 0) or 0)
            distance_matches = int(nlp_result.get('distance_matches', 0) or 0)

            if joint_matches >= 1:
                quality_factor = 1.0
            elif time_matches >= 1:
                quality_factor = 0.70
            elif distance_matches >= 1:
                quality_factor = 0.40
            else:
                quality_factor = 0.20

            eff_conf = base_conf * quality_factor

            # Global cap at 0.80
            eff_conf = min(eff_conf, 0.80)
            # Additional cap at 0.55 when there are no joint matches
            if joint_matches == 0:
                eff_conf = min(eff_conf, 0.55)

            return float(eff_conf)
        
        # Extract confidence values from each module
        cv_confidence = cv_score if cv_score is not None else None
        pg_confidence = float(pg_result.get('confidence', 0.5))
        nlp_confidence = _get_nlp_confidence(nlp_result) if nlp_result else 0.0
        
        # SANITY CHECK: Warn about suspicious CV confidence values
        if cv_confidence is not None:
            if cv_confidence >= 0.99:
                logger.warning(f"[DECISION] SUSPICIOUS: CV confidence is {cv_confidence:.4f} (suspiciously high!)")
                logger.warning(f"[DECISION] This may indicate the CV model produced an all-oil or all-non-oil mask")
                logger.warning(f"[DECISION] Check the CV mask file for quality issues")
                print(f"[DECISION] WARNING: CV confidence={cv_confidence:.4f} - possible model failure!")
            elif cv_confidence == 1.0:
                logger.critical(f"[DECISION] CV confidence is EXACTLY 1.0 - Model definitely wrong!")
                print(f"[DECISION] CRITICAL: CV confidence=1.0 - Model failure suspected")
        
        # REFACTORED: Separate Oil evidence from Non-Oil evidence
        # ========================================================
        
        # Get raw predictions from each model
        pg_label = pg_result.get('classification', 'Not performed')
        nlp_label = nlp_result.get('classification', nlp_result.get('label', '')) if nlp_result else ''
        
        # Normalize predictions with MODEL-SPECIFIC LOGIC
        # ===============================================
        
        # PG prediction: check classification string
        def _get_pg_prediction(label: str, confidence: float) -> str:
            """Convert PG classification to Oil or Non-Oil"""
            label_lower = str(label).lower()
            if 'false positive' in label_lower:
                return 'Non-Oil'  # False Positive → Non-Oil
            elif 'oil' in label_lower:
                return 'Oil'  # Oil-like → Oil
            else:
                # Fallback to confidence
                return 'Oil' if confidence >= 0.5 else 'Non-Oil'
        
        # NLP prediction: use risk_level (HIGH/MEDIUM=Oil, LOW/VERY_LOW=Non-Oil)
        def _get_nlp_prediction(nlp_result) -> str:
            """Convert NLP risk_level to Oil or Non-Oil"""
            if nlp_result is None:
                # No NLP information → neutral, treated as Non-Oil with 0.0 confidence
                return 'Non-Oil'
            risk_level = nlp_result.get('risk_level', 'LOW').upper()
            if risk_level in ['HIGH', 'MEDIUM']:
                return 'Oil'  # HIGH or MEDIUM risk → Oil-like
            else:
                return 'Non-Oil'  # LOW or VERY_LOW → Non-Oil
        
        # CV prediction: convert confidence into directional Oil/Non-Oil confidence
        def _get_cv_prediction(confidence: Optional[float]):
            """
            Convert CV confidence to (label, confidence).
            
            CV score is "probability detected pixels are oil", so:
            - Oil-like:  confidence = cv_score
            - Non-Oil:   confidence = 1 - cv_score
            """
            if confidence is None:
                return 'Non-Oil', 0.0
            if confidence > 0.5:
                return 'Oil', float(confidence)
            return 'Non-Oil', float(1.0 - confidence)
        
        # Apply model-specific logic
        pg_prediction = _get_pg_prediction(pg_label, pg_confidence)
        nlp_prediction = _get_nlp_prediction(nlp_result) if nlp_result else 'Non-Oil'
        cv_prediction, cv_effective_conf = _get_cv_prediction(cv_confidence)
        
        logger.info(f"[DECISION] Model-specific predictions - CV: {cv_prediction}, PG: {pg_prediction}, NLP: {nlp_prediction}")
        cv_raw_str = f"{cv_confidence:.2f}" if cv_confidence is not None else 'N/A'
        cv_eff_str = f"{cv_effective_conf:.2f}" if cv_confidence is not None else 'N/A'
        logger.info(
            f"[DECISION] Confidences - CV: raw={cv_raw_str}, eff={cv_eff_str}, "
            f"PG: {pg_confidence:.2f}, NLP: {f'{nlp_confidence:.2f}' if nlp_confidence else 'N/A'}"
        )
        
        # Accumulate evidence scores
        oil_evidence = 0.0
        nonoil_evidence = 0.0
        
        # CV model voting
        if cv_confidence is not None:
            if cv_prediction == 'Oil':
                oil_evidence += cv_effective_conf * self.cv_weight
                logger.info(
                    f"[DECISION] CV votes 'Oil' with evidence: {cv_effective_conf * self.cv_weight:.3f} "
                    f"(cv_score={cv_confidence:.3f})"
                )
            else:
                nonoil_evidence += cv_effective_conf * self.cv_weight
                logger.info(
                    f"[DECISION] CV votes 'Non-Oil' with evidence: {cv_effective_conf * self.cv_weight:.3f} "
                    f"(cv_score={cv_confidence:.3f}, non_oil_conf={cv_effective_conf:.3f})"
                )
        
        # PG model voting
        if pg_prediction == 'Oil':
            oil_evidence += pg_confidence * self.pg_weight
            logger.info(f"[DECISION] PG votes 'Oil' with evidence: {pg_confidence * self.pg_weight:.3f}")
        else:
            nonoil_evidence += pg_confidence * self.pg_weight
            logger.info(f"[DECISION] PG votes 'Non-Oil' with evidence: {pg_confidence * self.pg_weight:.3f}")
        
        # NLP model voting
        if nlp_result and nlp_confidence is not None:
            if nlp_prediction == 'Oil':
                oil_evidence += nlp_confidence * self.nlp_weight
                logger.info(f"[DECISION] NLP votes 'Oil' with evidence: {nlp_confidence * self.nlp_weight:.3f}")
            else:
                nonoil_evidence += nlp_confidence * self.nlp_weight
                logger.info(f"[DECISION] NLP votes 'Non-Oil' with evidence: {nlp_confidence * self.nlp_weight:.3f}")
        
        # Compute final decision
        logger.info(f"[DECISION] Total Oil evidence: {oil_evidence:.3f}")
        logger.info(f"[DECISION] Total Non-Oil evidence: {nonoil_evidence:.3f}")
        
        # Majority veto: if both CV and PG vote Non-Oil, force Non-oil regardless of NLP
        if cv_prediction == 'Non-Oil' and pg_prediction == 'Non-Oil':
            final_prediction = "Non-oil"
            final_confidence = nonoil_evidence
            decision_basis = "Majority veto: CV and PG both vote Non-Oil"
        elif oil_evidence > nonoil_evidence and oil_evidence >= self.confidence_threshold:
            final_prediction = "Oil-like"
            final_confidence = oil_evidence
            decision_basis = (f"Oil evidence ({oil_evidence:.3f}) > Non-Oil evidence ({nonoil_evidence:.3f}) "
                              f"and >= confidence threshold ({self.confidence_threshold:.2f})")
        else:
            # Either Non-Oil evidence dominates, or Oil evidence is below minimum confidence gate
            final_prediction = "Non-oil"
            final_confidence = nonoil_evidence
            if oil_evidence > nonoil_evidence:
                decision_basis = (f"Oil evidence ({oil_evidence:.3f}) > Non-Oil evidence ({nonoil_evidence:.3f}) "
                                  f"but below confidence threshold ({self.confidence_threshold:.2f})")
            else:
                decision_basis = (f"Non-Oil evidence ({nonoil_evidence:.3f}) >= Oil evidence ({oil_evidence:.3f})")
        
        logger.info(f"[DECISION] Final Decision: {final_prediction} (confidence: {final_confidence:.3f})")
        logger.info(f"[DECISION] Decision Basis: {decision_basis}")
        
        # Create model decisions for detailed tracking
        decisions = []
        
        if cv_confidence is not None:
            decisions.append(ModelDecision(
                model_name="CV Detection",
                prediction=cv_prediction,
                confidence=cv_effective_conf,
                weight=self.cv_weight
            ))
        
        decisions.append(ModelDecision(
            model_name="Physics-Guided",
            prediction=pg_prediction,
            confidence=pg_confidence,
            weight=self.pg_weight
        ))
        
        if nlp_result and nlp_confidence is not None:
            nlp_risk_level = nlp_result.get('risk_level', 'LOW')
            decisions.append(ModelDecision(
                model_name="NLP",
                prediction=nlp_prediction,
                confidence=nlp_confidence,
                weight=self.nlp_weight
            ))
        
        # Create detailed summary with evidence breakdown
        summary = {
            'oil_evidence': float(oil_evidence),
            'nonoil_evidence': float(nonoil_evidence),
            'decision_basis': decision_basis,
            'decision_method': 'Separated Evidence Voting (Fixed)',
            'model_votes': {
                'Physics-Guided': {
                    'prediction': pg_prediction,
                    'confidence': float(pg_confidence),
                    'weight': float(self.pg_weight),
                    'contribution': float(pg_confidence * self.pg_weight),
                    'category': 'Oil' if pg_prediction == 'Oil' else 'Non-Oil'
                }
            }
        }
        
        # Add CV to summary if available
        if cv_confidence is not None:
            summary['model_votes']['CV Detection'] = {
                'prediction': cv_prediction,
                'confidence': float(cv_effective_conf),
                'weight': float(self.cv_weight),
                'contribution': float(cv_effective_conf * self.cv_weight),
                'category': 'Oil' if cv_prediction == 'Oil' else 'Non-Oil'
            }
        
        # Add NLP to summary if available
        if nlp_result and nlp_confidence is not None:
            summary['model_votes']['NLP'] = {
                'prediction': nlp_prediction,
                'risk_level': nlp_result.get('risk_level', 'UNKNOWN'),
                'confidence': float(nlp_confidence),
                'weight': float(self.nlp_weight),
                'contribution': float(nlp_confidence * self.nlp_weight),
                'category': 'Oil' if nlp_prediction == 'Oil' else 'Non-Oil',
                'matches': {
                    'distance': nlp_result.get('distance_matches', 0),
                    'time': nlp_result.get('time_matches', 0),
                    'joint': nlp_result.get('joint_matches', 0)
                }
            }
        
        return EnsembleDecision(
            final_prediction=final_prediction,
            final_confidence=final_confidence,
            individual_decisions=decisions,
            decision_summary=summary
        )
    
    @staticmethod
    def _get_score(classification: str) -> float:
        """Convert classification string to numerical score"""
        oil_keywords = ["oil", "oil-like", "1"]
        if any(keyword in str(classification).lower() for keyword in oil_keywords):
            return 1.0
        return 0.0
    
    def to_dict(self, ensemble_decision: EnsembleDecision) -> Dict:
        """Convert ensemble decision to dictionary for JSON serialization"""
        return {
            'final_prediction': ensemble_decision.final_prediction,
            'final_confidence': ensemble_decision.final_confidence,
            'individual_decisions': [
                {
                    'model_name': d.model_name,
                    'prediction': d.prediction,
                    'confidence': d.confidence,
                    'weight': d.weight
                }
                for d in ensemble_decision.individual_decisions
            ],
            'decision_summary': ensemble_decision.decision_summary
        }


def make_ensemble_decision(
    pg_result: Dict,
    nlp_result: Optional[Dict] = None,
    cv_score: Optional[float] = None,
    weights: Optional[Dict] = None
) -> Dict:
    """
    Convenience function to make ensemble decision combining CV, PG, and NLP
    
    Parameters:
    -----------
    pg_result : dict
        Physics-Guided classifier result
    nlp_result : dict, optional
        NLP classifier result
    cv_score : float, optional
        CV detection confidence score
    weights : dict, optional
        Custom weights {'cv': 0.4, 'pg': 0.3, 'nlp': 0.3}
    
    Returns:
    --------
    dict
        Final decision as dictionary
    """
    if weights is None:
        # Updated default weights reflecting CV/PG primacy and NLP as corroborating signal
        weights = {'cv': 0.45, 'pg': 0.35, 'nlp': 0.20}
    
    decision_layer = DecisionLayer(
        pg_weight=weights.get('pg', 0.35),
        nlp_weight=weights.get('nlp', 0.20),
        cv_weight=weights.get('cv', 0.45)
    )
    
    ensemble_decision = decision_layer.decide(pg_result, nlp_result, cv_score=cv_score)
    
    return decision_layer.to_dict(ensemble_decision)