from aiida.engine import WorkChain
from aiida.orm import SinglefileData


class CharacterizerWorkChain(WorkChain):
    @classmethod
    def define(cls, spec):
        super().define(spec)

        spec.input(
            "config",
            valid_type=SinglefileData,
            help="A CharLib configuration YAML file containing characterization settings and cell configurations",
        )
        spec.outline(
            cls.load_config,
            cls.map_procedures,
            cls.run_procedures,
            cls.merge_results,
        )
        spec.output(
            "liberty_result", valid_type=SinglefileData, help="A liberty file containing characterization results"
        )

    def load_config(self):
        """Read the config file and create or load nodes from the database"""
        pass  # TODO

    def map_procedures(self):
        """Iterate over cells in the config and identify which procedures we can run with the given parameters"""
        pass  # TODO

    def run_procedures(self):
        """Run previously mapped procedures with as much parallelism as possible"""
        pass  # TODO

    def merge_results(self):
        """Collect all procedures' results and merge them into a liberty file for the whole cell library"""
        pass  # TODO
