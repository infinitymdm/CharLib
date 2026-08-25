from abc import abstractmethod

from aiida.engine import WorkChain


class Procedure(WorkChain):
    """Abstract base class for Procedures"""

    @classmethod
    def define(cls, spec):
        """Specify common inputs and outputs. Subclasses should use this in addition to their own define methods"""
        super().define(spec)

        # TODO: Define cell & input, liberty output

    @abstractmethod
    @classmethod
    def is_applicable(cls, cell_config):
        """Check whether the given cell config has all required parameters for this procedure"""
        pass

    @abstractmethod
    def build_netlist(self):
        """Build one or more SPICE netlists for later simulation"""
        pass

    @abstractmethod
    def write_liberty(self):
        """Annotate the liberty group with this procedure's simulation results"""
        pass
