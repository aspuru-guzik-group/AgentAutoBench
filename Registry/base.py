# Auto_benchmark/registry/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List, Optional

from Auto_benchmark.io import fs
from Auto_benchmark.Config import defaults

class BenchmarkJob(ABC):
    """
    Abstract Base Class for all benchmark jobs.
    Encapsulates the workflow: Scan -> Extract -> Score.
    """
    def __init__(self, root_dir: Path, debug: bool = False):
        """
        Initialize the benchmark job.

        Args:
            root_dir (Path): The root directory of the dataset.
            debug (bool): Enable debug logging.
        """
        self.root = Path(root_dir)
        self.debug = debug
        if not self.root.exists():
            raise FileNotFoundError(f"Root path not found: {self.root}")
        self.rubric = self.load_rubric()

    @abstractmethod
    def load_rubric(self) -> Dict[str, Any]:
        """
        Return the rubric dictionary for this job.

        Returns:
            Dict[str, Any]: The rubric configuration.
        """
        pass

    def find_report(self) -> Optional[Path]:
        """
        Locate the agent's markdown report using standard heuristics.
        
        Returns:
            Optional[Path]: Path to the report file, or None if not found.
        """
        candidates = sorted(self.root.glob("*.md"))
        rep_dir = self.root / defaults.REPORT_DIR_NAME
        if rep_dir.is_dir():
            candidates += sorted(rep_dir.glob("*.md"))
            
        if not candidates:
            return None
            
        by_name = {p.name: p for p in candidates}
        for name in defaults.REPORT_FILENAMES:
            if name in by_name:
                return by_name[name]
        
        # Fallback: Largest file
        return max(candidates, key=lambda p: p.stat().st_size)

    def scan_folders(self) -> List[Path]:
        """
        Identify relevant folders. 
        Default behavior: Use structure-based representatives (InChIKey).

        Returns:
            List[Path]: A list of folder paths to process.
        """
        return fs.select_unique_by_inchikey(self.root, prefer_real_freqs=True)

    @abstractmethod
    def check_inputs(self, context: Any) -> Dict[str, Any]:
        """
        Step 1: Perform input validity checks.
        
        Args:
            context (Any): Job-specific context (e.g., file mapping).
            
        Returns:
            Dict[str, Any]: Boolean results for input checks.
        """
        pass
    
    @abstractmethod
    def check_outputs(self, context: Any) -> Dict[str, Any]:
        """
        Step 2: Perform output validity checks.
        
        Args:
            context (Any): Job-specific context (e.g., file mapping).
            
        Returns:
            Dict[str, Any]: Boolean results for output checks.
        """
        pass
    
    @abstractmethod
    def calculate_ground_truth(self, context: Any) -> Dict[str, Any]:
        """
        Step 3: Calculate ground truth values from the outputs.
        
        Args:
            context (Any): Job-specific context (e.g., file mapping).
            
        Returns:
            Dict[str, Any]: The calculated ground truth data.
        """
        pass

    @abstractmethod
    def process_folder(self, folder: Path) -> Dict[str, Any]:
        """
        Extract data (Booleans + Ground Truth) from a single folder.
        Combine funtion as the following steps ideally: 
        1. check_inputs
        2. check_outputs
        3. calculate_ground_truth

        Args:
            folder (Path): The folder to process.

        Returns:
            Dict[str, Any]: Extracted data. Must contain at least "Folder".
        """
        pass

    @abstractmethod
    def extract_agent_data(self, report_path: Optional[Path]) -> Dict[str, Any]:
        """
        Extract agent answers from the report markdown.

        Args:
            report_path (Optional[Path]): Path to the agent's report.

        Returns:
            Dict[str, Any]: Extracted agent data.
        """
        pass

    @abstractmethod
    def score_all(self, folder_results: List[Dict[str, Any]], agent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate final scores from all processed folders and agent data.

        Args:
            folder_results (List[Dict]): List of results from process_folder().
            agent_data (Dict): Data extracted from the report.

        Returns:
            Dict[str, Any]: The final scoring result payload.
        """
        pass
    
    @abstractmethod
    def run(self) -> Dict[str, Any]:
        """
        Main execution template method.
        
        Returns:
            Dict[str, Any]: The complete benchmark result.
        """
        pass
