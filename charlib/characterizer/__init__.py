from aiida.engine import WorkChain
from aiida.orm import SinglefileData


class CharacterizerWorkChain(WorkChain):
    @classmethod
    def define(cls, spec):
        super().define(spec)

        spec.input(
            "config_file",
            valid_type=SinglefileData,
            help="A CharLib configuration YAML file containing characterization settings and cell configurations",
        )
        spec.outline(
            cls.load_config,
            cls.run_measurements,
            cls.merge_results,
        )
        spec.output(
            "liberty_result", valid_type=SinglefileData, help="A liberty file containing characterization results"
        )

    def load_config(self):
        pass  # TODO

    def run_measurements(self):
        pass  # TODO

    def merge_results(self):
        pass  # TODO
