from abc import ABC, abstractmethod
from charlib.characterizer.cell import Cell, CellTestConfig
from dataclasses import dataclass
from enum import Enum, auto
import itertools
import json
from pathlib import Path
from typing import Any, Generator, Union

registered_procedures = {}


def register(*parameters):
    """
    Decorator to register a procedure (and any required parameters) with the Characterizer.

    If used as a decorator with string arguments, each arg will be added to the list of supported
    parameters for CellTestConfig.
    """
    # When used without parentheses: @register
    if len(parameters) == 1 and callable(parameters[0]):
        procedure = parameters[0]
        registered_procedures[procedure.__name__] = {
            'callable': procedure,
            'parameters': ()
        }
        return procedure

    # When used with parentheses: @register('fizz', 'buzz')
    def decorator_with_args(procedure):
        registered_procedures[procedure.__name__] = {
            'callable': procedure,
            'parameters': parameters
        }
        return procedure
    return decorator_with_args


class ProcedureFailedException(Exception):
    """Indicates that the procedure failed for the reason specified in the message."""
    pass


@dataclass(frozen=True)
class Variation:
    """Frozen hashable dataclass for capturing a unique set of simulation conditions.

    Stores variation conditions as a frozenset of 2-tuples, e.g. {('temperature', 25.0), ('load', 1.2)}.
    """
    conditions: frozenset[tuple[str, str|float]]

    def to_path_slug(self) -> str:
        """Construct a deterministic, filesystem-safe string by sorting condition keys."""
        sorted_conditions = sorted(self.conditions, key=lambda x: x[0])
        return '__'.join(f'{k}-{v}' for k, v in sorted_conditions)


@dataclass
class SimulationConfig:
    target: Cell
    config: CellTestConfig
    settings: Any


@dataclass
class SimulationResult:
    """Represents a set of measurements from a simulation tagged with the variation"""
    variation: Variation            # The unique variation for this result
    measurements: dict[str, float]  # Named measurements produced by the simulation
    success: bool                   # Whether the simulation completed without any errors


class NodeState(Enum):
    PENDING = auto()    # awaiting dependencies
    READY = auto()      # dependencies met, ready to execute
    RUNNING = auto()    # currently in thread pool
    SUSPENDED = auto()  # waiting on a sub-node yielded by an AdaptiveSimulationNode
    COMPLETED = auto()  # finished with a SimulationResult


class SimulationNode(ABC):
    """Base class representing a single unit of execution within a directed acyclic graph."""
    def __init__(self, config: SimulationConfig, variation: Variation, work_dir: Path):
        self.config = config
        self.variation = variation
        self.work_dir = work_dir
        self.dependencies: set['SimulationNode'] = set()

    def add_dependency(self, node: 'SimulationNode'):
        """Register an upstream node as prerequisite for this node."""
        self.dependencies.add(node)

    def __hash__(self):
        """Hash nodes by class and variation."""
        return hash((self.__class__.__name__, self.variation))

    def __eq__(self, other):
        if not isinstance(other, SimulationNode):
            return False
        return self.__class__.__name__ == other.__class__.__name__ and self.variation == other.variation

    def _is_cached(self) -> bool:
        """Check if a valid payload result already exists."""
        return (self.work_dir / 'result.pkl').exists()

    def _load_cache(self) -> SimulationResult:
        with open(self.work_dir / 'result.pkl', 'rb') as f:
            data = json.load(f)
            return SimulationResult(self.variation, data['measurements'], data['success'])

    def _save_cache(self, result: SimulationResult) -> None:
        with open(self.work_dir / 'result.pkl', 'wb') as f:
            json.dump({'measurements': result.measurements, 'success': result.success}, f)

    def execute(self, dependency_results: dict['SimulationNode', SimulationResult], clobber: bool = False) -> Union[SimulationResult, Generator]:
        """Run simulation (with cache short-circuiting) and return the results."""
        if not clobber and self._is_cached():
            return self._load_cache()

        self.work_dir.mkdir(parents=True, exist_ok=True)
        result = self._run_simulation(dependency_results)
        self._save_cache(result) # FIXME: Handle the case where result is a generator (i.e. this is an adaptive node)
        return result

    @abstractmethod
    def _run_simulation(self, dependency_results: dict['SimulationNode', SimulationResult]) -> Union[SimulationResult, Generator]:
        """Core logic implemented by subclasses. Accepts resolved upstream data and returns results."""
        pass


class AdaptiveSimulationNode(SimulationNode):
    """Represents a node which may generate other SimulationNodes as the result of its execution.

    This should be used for Procedures where the number of intermediate steps cannot be determined
    prior to execution, such as when using a genetic algorithm to determine test points.
    """

    @abstractmethod
    def _run_simulation(self, dependency_results: dict['SimulationNode', SimulationResult]) -> Generator[SimulationNode, SimulationResult]:
        """Yields SimulationNodes that must be evaluated by the orchestrator.

        The orchestrator sends the SimulationResult back into the generator for use by the next
        iteration or possibly for return as a final result.
        """
        pass


class Procedure(ABC):
    """Stateless factory responsible for validating config and building graphs for measurements."""

    @classmethod
    @abstractmethod
    def variation_params(cls) -> list:
        """Return a list of parameter names used to define variations of this procedure.

        These parameters are used during DAG generation to construct unique variations for each
        combination of values.
        """
        pass

    @classmethod
    @abstractmethod
    def runtime_params(cls) -> list:
        """Return a list of parameter names used at runtime in this procedure.

        These parameters are not used to construct new variations, but must be defined in order
        to run this procedure. Often these parameters will have reasonable defaults that don't
        need to be adjusted by the user.
        """
        pass

    @classmethod
    def params(cls) -> list:
        """Return a list of all parameter names"""
        return cls.variation_params() + cls.runtime_params()

    @classmethod
    def vary_config_params(cls, config: CellTestConfig):
        """Generate all unique parameter combinations from a config"""
        param_names, values = zip(*[(k, config.parameters[k]) for k in cls.params()])
        for combination in itertools.product(*[v if isinstance(v, list) else [v] for v in values]):
            yield zip(param_names, combination)

    @classmethod
    @abstractmethod
    def is_applicable(cls, config: SimulationConfig) -> bool:
        """Check whether the targeted cell is compatible with this procedure.

        This step should involve at least two checks:
        1. Verifying that the cell has the required I/O to stimulate
        2. Verifying that the config contains all required parameters (runtime and variation)
        """
        pass

    @classmethod
    @abstractmethod
    def generate_dag(cls, config: SimulationConfig) -> set[SimulationNode]:
        """Generate a DAG representing the steps for this procedure's variations.

        Generates variations from parameter combinations, instantiates SimulationNodes, map their
        dependencies, assigns unique working directories, and returns the terminal nodes of the
        directed acyclic graph.
        """
        pass
