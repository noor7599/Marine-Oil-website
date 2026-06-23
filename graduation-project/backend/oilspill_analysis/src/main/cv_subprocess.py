"""
CV Model Subprocess Wrapper
Calls MariNeXt CV model in separate 'mados' conda environment
Data exchange via JSON + NPY files
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Tuple, Optional, Dict

class CVSubprocessRunner:
    """Wrapper to run CV model in separate conda environment."""
    
    def __init__(self, conda_env: str = "mados", workspace_root: Optional[str] = None):
        """
        Initialize CV subprocess runner.
        
        Args:
            conda_env: Name of conda environment with CV dependencies (default: mados)
            workspace_root: Root path of the project (auto-detected if None)
        """
        self.conda_env = conda_env
        self.workspace_root = Path(workspace_root) if workspace_root else self._find_workspace()
        self.temp_dir = self.workspace_root / "temp"
        self.cv_script = self.workspace_root / "src" / "cv" / "run_cv.py"
        self.config_path = self.workspace_root / "config.json"
        
        # --- MAC FIX START ---
        # If the temp directory doesn't exist, create it so validation passes
        if not self.temp_dir.exists():
            self.temp_dir.mkdir(parents=True, exist_ok=True)
        # --- MAC FIX END ---
        
        self._validate_setup()
    
    def _find_workspace(self) -> Path:
        """Auto-detect workspace root by finding config.json."""
        current = Path.cwd()
        for parent in [current] + list(current.parents):
            if (parent / "config.json").exists() and (parent / "src").exists():
                return parent
        raise RuntimeError("Could not find workspace root. Please pass workspace_root explicitly.")
    
    def _validate_setup(self):
        """Validate required files and directories exist."""
        errors = []
        
        if not self.cv_script.exists():
            errors.append(f"CV script not found: {self.cv_script}")
        if not self.config_path.exists():
            errors.append(f"Config not found: {self.config_path}")
        if not self.temp_dir.exists():
            errors.append(f"Temp directory not found: {self.temp_dir}")
        
        if errors:
            raise RuntimeError("Setup validation failed:\n- " + "\n- ".join(errors))
    
    def run_inference(self, image_path: str) -> Tuple[bool, Dict]:
        """
        Run CV inference via subprocess in mados environment.
        """
        image_path = Path(image_path)
        if not image_path.exists():
            return False, {"error": f"Image not found: {image_path}"}
        
        output_dir = self.temp_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Build conda run command
        # Use .resolve() to handle absolute paths and spaces correctly on Mac
        image_path_abs = str(image_path.resolve())
        output_dir_abs = str(output_dir.resolve())
        cv_script_abs = str(self.cv_script.resolve())
        
        # Construct command
        if sys.platform == "win32":
            # On Windows, use double quotes and ensure proper escaping
            cmd = f'conda run -n {self.conda_env} python "{cv_script_abs}" --input "{image_path_abs}" --output "{output_dir_abs}"'
        else:
            # --- MAC FIX START ---
            # On Mac, we use a list. Python handles the spaces in "all project" automatically this way.
            cmd = [
                "conda", "run", "-n", self.conda_env,
                "python", cv_script_abs,
                "--input", image_path_abs,
                "--output", output_dir_abs
            ]
            # --- MAC FIX END ---
        
        try:
            print(f"[CV] Running: {cmd if isinstance(cmd, str) else ' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 min timeout
                shell=isinstance(cmd, str)  # Use shell only when cmd is a string (Windows)
            )
            
            # Read result JSON
            result_path = output_dir / "cv_results.json"
            if not result_path.exists():
                return False, {"error": f"CV script did not produce result. stderr: {result.stderr}"}
            
            with open(result_path) as f:
                cv_result = json.load(f)
            
            if result.returncode != 0:
                return False, cv_result
            
            return True, cv_result
        
        except subprocess.TimeoutExpired:
            return False, {"error": "CV inference timed out (>5 min)"}
        except Exception as e:
            return False, {"error": f"Subprocess failed: {str(e)}"}
    
    def check_environment(self) -> Tuple[bool, str]:
        """
        Verify that mados conda environment is installed and has dependencies.
        """
        # MAC FIX: On Mac, we don't use shell=True for this check as it can fail to find 'conda'
        cmd = ["conda", "run", "-n", self.conda_env, "python", "-c", 
               "import torch; import mmseg; print('OK')"]
        
        try:
            # We remove shell=True here for Mac stability
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and "OK" in result.stdout:
                return True, f"Environment '{self.conda_env}' is ready"
            else:
                return False, f"Environment '{self.conda_env}' exists but missing dependencies:\n{result.stderr}"
        except Exception as e:
            return False, f"Conda environment '{self.conda_env}' not found or not accessible: {str(e)}"


def infer_cv(image_path: str, workspace_root: Optional[str] = None, 
             conda_env: str = "mados") -> Tuple[Optional[str], Optional[float]]:
    """
    Convenience function: run CV inference and return mask path + confidence.
    """
    runner = CVSubprocessRunner(conda_env=conda_env, workspace_root=workspace_root)
    
    success, result = runner.run_inference(image_path)
    
    if not success:
        print(f"[CV ERROR] {result.get('error', 'Unknown error')}", file=sys.stderr)
        return None, None
    
    return result.get("mask_path"), result.get("confidence")


if __name__ == "__main__":
    # Test: python cv_subprocess.py <image_path> [workspace_root]
    if len(sys.argv) < 2:
        print("Usage: python cv_subprocess.py <image_path> [workspace_root]")
        sys.exit(1)
    
    image_path = sys.argv[1]
    workspace_root = sys.argv[2] if len(sys.argv) > 2 else None
    
    runner = CVSubprocessRunner(workspace_root=workspace_root)
    
    # Check environment first
    env_ok, env_msg = runner.check_environment()
    print(f"[CV] {env_msg}")
    
    if not env_ok:
        sys.exit(1)
    
    # Run inference
    success, result = runner.run_inference(image_path)
    
    if success:
        print(f"[CV] Success! Mask saved to: {result['mask_path']}")
        print(f"[CV] Confidence: {result['confidence']}")
    else:
        print(f"[CV] Failed: {result.get('error', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)