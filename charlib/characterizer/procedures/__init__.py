from abc import ABC, abstractmethod
from pathlib import Path
import pickle

from charlib.liberty.liberty import Group

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


class Procedure(ABC):
    """Abstract base class representing a Procedure"""

    @classmethod
    @abstractmethod
    def variation_params(cls) -> list:
        """Return a list of parameter names used to define variations of this procedure."""
        pass

    @classmethod
    @abstractmethod
    def runtime_params(cls) -> list:
        """Return a list of parameter names used at runtime in this procedure."""
        pass

    @classmethod
    @abstractmethod
    def measurements(cls):
        """Return a liberty object describing the measurements this procedure provides."""
        pass

    @classmethod
    @abstractmethod
    def check_target(self, cell, config) -> bool:
        """Check whether the targeted cell is compatible with this procedure."""
        pass

    @classmethod
    @abstractmethod
    def generate(cls, cell, config, settings):
        """Generate directed graphs of procedures required to make relevant measurements."""
        pass

    @abstractmethod
    def simulate(self, cell, settings):
        """Run simulations to populate self.liberty"""
        pass

    def __call__(self, *args, **kwargs):
        """Run the simulations associated with this procedure instance"""
        if kwargs.get('clobber'):
            self.simulate(*args, **kwargs)
            self.export_results()
            return self.liberty
        try:
            self.load_results()
        except FileNotFoundError:
            self.simulate(*args, **kwargs)
            self.export_results()
        return self.liberty

    @property
    def target_cell_name(self) -> str:
        """Return the name of the targeted cell"""
        return self._target_cell_name

    @property
    def variation(self) -> dict:
        """Return a dict of parameter-value pairs that uniquely define this procedure instance."""
        return self._variation

    @property
    def liberty(self):
        """Return the liberty results for this procedure.

        If the procedure has not yet been run, this contains a 'skeleton' liberty object not yet
        populated with results. If simulation is already complete, this returns the populated
        liberty object.
        """
        return self._liberty

    def get_workdir(self) -> Path:
        """Return the name of this procedure's unique work directory"""
        config_str = '__'.join([f'{k}_{v}' for k, v in self.variation.items()])
        return Path(self.target_cell_name) / self.__name__ / config_str

    def export_results(self):
        """Write this procedure's liberty results to the work directory"""
        workdir = self.get_workdir()
        workdir.mkdir(parents=True, exist_ok=True)
        with open(workdir / 'result.lib.pkl', 'wb') as result_file:
            pickle.dump(self.liberty)

    def load_results(self):
        """Load this procedure's liberty results from the work directory"""
        with open(self.get_workdir() / 'result.lib.pkl', 'rb') as result_file:
            return pickle.load(result_file)
