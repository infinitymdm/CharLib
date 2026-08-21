from collections.abc import Generator
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Union


@dataclass
class CellConfig:
    cell: Cell
    settings: Any
    parameters: dict[str, list]


@dataclass
class SimulationResult:
    """Represents a set of measurements from a simulation tagged with the variation"""
    variation: Variation            # The unique variation for this result
    measurements: dict[str, float]  # Named measurements produced by the simulation
    success: bool                   # Whether the simulation completed without any errors


class SimulationNode(Node):
    """Represents a single SPICE simulation."""
    def __init__(self, config: CellConfig, variation: Variation):
        super().__init__()
        self.config = config
        self.variation = variation

    def __hash__(self):
        """Hash nodes by class and variation."""
        return hash((self.__class__.__name__, self.variation))

    def __eq__(self, other):
        if not isinstance(other, SimulationNode):
            return False
        return self.__class__.__name__ == other.__class__.__name__ and self.variation == other.variation

    def work_dir(self) -> Path:
        return self.config.cell.name / self.__class__.__name__ / self.variation.to_path_slug()

    def _is_cached(self) -> bool:
        """Check if a valid payload result already exists."""
        return (self.work_dir() / 'result.json').exists()

    def _load_cache(self) -> SimulationResult:
        with open(self.work_dir() / 'result.json', 'r') as f:
            data = json.load(f)
            return SimulationResult(self.variation, data['measurements'], data['success'])

    def _save_cache(self, result: SimulationResult) -> None:
        with open(self.work_dir() / 'result.json', 'w') as f:
            json.dump({'measurements': result.measurements, 'success': result.success}, f)

    def execute(self, dependency_results: dict['Node', Any], clobber: bool = False) -> Union[SimulationResult, Generator]:
        """Run simulation (with cache short-circuiting) and return the results."""
        if not clobber and self._is_cached():
            return self._load_cache()

        self.work_dir().mkdir(parents=True, exist_ok=True)
        result = self._run_simulation(dependency_results)
        self._save_cache(result) # FIXME: Handle the case where result is a generator (i.e. this is an adaptive node)
        return result

    @abstractmethod
    def _run_simulation(self, dependency_results: dict['SimulationNode', SimulationResult]) -> Union[SimulationResult, Generator]:
        """Core logic implemented by subclasses. Accepts resolved upstream data and returns results."""
        pass
