from abc import abstractmethod
from collections.abc import Iterable
from charlib.characterizer.procedures import SimulationNode, SimulationResult
from typing import Dict
import numpy as np

class AggregatorNode(SimulationNode):
    """Find a single aggregate value representative of a range of inputs"""

    @abstractmethod
    def aggregate(self, inputs: Iterable[float|int]) -> float:
        """Select or aggregate one result from a collection of results"""
        pass

    def _run_simulation(self, dependency_results: Dict['SimulationNode', SimulationResult]) -> SimulationResult:
        """Aggregate results from dependencies and return single result"""
        measurements = {}
        for key in set.intersection(*map(set, [i.measurements for i in dependency_results.values()])):
            measurements[key] = self.aggregate([i.measurements[key] for i in dependency_results.values()])
        return SimulationResult(self.variation, measurements, True)


class MeanNode(AggregatorNode):
    """Find the mean of a range of results"""
    def aggregate(self, inputs: Iterable[float|int]) -> float:
        """Compute the mean of the inputs"""
        return np.mean(inputs)


class MaxNode(AggregatorNode):
    """Find the max of a range of results"""
    def aggregate(self, inputs: Iterable[float|int]) -> float:
        """Compute the maximum of the inputs"""
        return max(inputs)


class MinNode(AggregatorNode):
    """Find the min of a range of results"""
    def aggregate(self, inputs: Iterable[float|int]) -> float:
        """Compute the minimum of the inputs"""
        return min(inputs)
