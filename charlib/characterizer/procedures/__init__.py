from abc import ABC, abstractmethod
from dataclasses import dataclass
import itertools
from typing import Any


class Node(ABC):
    """Abstract class representing an executable node on a directed graph."""
    def __init__(self):
        self.dependencies: set['Node'] = set()

    def add_dependency(self, node: 'Node') -> None:
        """Register an upstream prerequisite for this node."""
        self.dependencies.add(node)

    @abstractmethod
    def __hash__(self):
        pass

    @abstractmethod
    def __eq__(self, other):
        pass

    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
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


# FIXME: Build base procedure
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
    def vary_config_params(cls, config: CellConfig):
        """Generate all unique parameter combinations from a config"""
        param_names, values = zip(*[(k, config.parameters[k]) for k in cls.params()])
        for combination in itertools.product(*[v if isinstance(v, list) else [v] for v in values]):
            yield zip(param_names, combination)

    @classmethod
    @abstractmethod
    def is_applicable(cls, config: CellConfig) -> bool:
        """Check whether the targeted cell is compatible with this procedure.

        This step should involve at least two checks:
        1. Verifying that the cell has the required I/O to stimulate
        2. Verifying that the config contains all required parameters (runtime and variation)
        """
        pass

    @classmethod
    @abstractmethod
    def generate_dag(cls, config: CellConfig) -> set[SimulationNode]:
        """Generate a DAG representing the steps for this procedure's variations.

        Generates variations from parameter combinations, instantiates SimulationNodes, map their
        dependencies, assigns unique working directories, and returns the terminal nodes of the
        directed acyclic graph.
        """
        pass
