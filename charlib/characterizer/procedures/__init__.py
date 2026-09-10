import hashlib
from pathlib import Path

from aiida.engine import WorkChain
from aiida.orm import Code, Dict, Float, SinglefileData, Str

from charlib.characterizer.procedures import utils
from charlib.characterizer.procedures.utils import QuantityData


class CharacterizationProcedure(WorkChain):
    """Abstract base class for all characterization Procedures"""

    @classmethod
    def define(cls, spec):
        """Specify common inputs and outputs. Subclasses will likely define additional I/O."""
        super().define(spec)

        # Cell
        spec.input("cell.name", valid_type=Str, help="Cell name as it appears in the netlist")
        spec.input("cell.netlist", valid_type=SinglefileData, help="The spice netlist for the cell")
        spec.input("cell.functions", valid_type=Dict, help="Boolean functions for each cell output")
        spec.input("cell.ports", valid_type=Dict, help="Port names and metadata")

        # Simulation settings
        spec.input("settings.simulation.engine", valid_type=Code, help="The spice engine used to perform simulations")
        spec.input_namespace(
            "settings.models",
            dynamic=True,
            required=False,
            validator=validate_models,
            help=(
                "Device models imported with .lib or .include directives. These are typically PDK-defined transistor "
                "models used in cell subcircuit definitions."
            ),
        )
        spec.input("settings.simulation.temperature", valid_type=QuantityData)

        # Units
        spec.input("settings.units.time", valid_type=Str)
        spec.input("settings.units.voltage", valid_type=Str)
        spec.input("settings.units.current", valid_type=Str)
        spec.input("settings.units.resistance", valid_type=Str)
        spec.input("settings.units.capacitance", valid_type=Str)
        spec.input("settings.units.power", valid_type=Str)
        spec.input("settings.units.energy", valid_type=Str)

        # Logic thresholds
        spec.input("settings.logic_thresholds.high", valid_type=Float)
        spec.input("settings.logic_thresholds.low", valid_type=Float)
        spec.input("settings.logic_thresholds.rise", valid_type=Float)
        spec.input("settings.logic_thresholds.fall", valid_type=Float)

        # Named nodes
        spec.input("settings.named_nodes.power.name", valid_type=Str)
        spec.input("settings.named_nodes.power.voltage", valid_type=QuantityData)
        spec.input("settings.named_nodes.ground.name", valid_type=Str)
        spec.input("settings.named_nodes.ground.voltage", valid_type=QuantityData)
        spec.input("settings.named_nodes.pwell.name", valid_type=Str)
        spec.input("settings.named_nodes.pwell.voltage", valid_type=QuantityData)
        spec.input("settings.named_nodes.nwell.name", valid_type=Str)
        spec.input("settings.named_nodes.nwell.voltage", valid_type=QuantityData)

        # Subclasses must define outline

        # Output a pickled liberty cell group
        spec.output(
            "liberty",
            valid_type=SinglefileData,
            help="A pickled liberty cell group annotated with this procedure's results.",
        )

    def setup_initial_netlist(self):
        """Perform common netlist setup tasks.

        This routine performs the following steps and places the resulting List entry in self.ctx.initial_netlist:
        1. Add include/lib statements for each model
        2. Initilize voltage supplies from settings.named_nodes
        """
        # Add model imports

        # Build voltage supplies
        named_nodes = self.inputs.settings.named_nodes
        supplies = [
            utils.create_vpower(named_nodes.power.name, named_nodes.power.voltage),
            utils.create_vground(named_nodes.ground.name, named_nodes.ground.voltage),
            utils.create_vpwell(named_nodes.pwell.name, named_nodes.pwell.voltage),
            utils.create_vnwell(named_nodes.nwell.name, named_nodes.nwell.voltage),
        ]
        self.ctx.initial_netlist = utils.combine_lists(*supplies)


def validate_models(value, port):  # noqa: PLR0911
    """Validate inputs to the models namespace.

    Each valid models entry has the following items:
    - 'path': a valid path Str which points to an extant file
    - 'hash': a Str which matches the hexadecimal hash of the file at 'path'
    - 'hash_algorithm': an optional Str specifying hash algorithm used to generate 'hash'. Defaults to sha3_256.
    - 'section': an optional Str. If provided, imports use ".lib <path> <section>."; otherwise ".inc <path>".
    """
    for label, group in value.items():
        # Check that path exists
        if "path" not in group:
            return f"Missing required input 'path' under 'settings.models.{label}'."
        if not isinstance(group["path"], Str):
            return f"'settings.models.{label}.path' must be of type Str, got {type(group['path']).__name__}."
        path = Path(group["path"].value).resolve()
        if not path.is_file():
            return f"'settings.models.{label}.path' does not contain a path to an extant file."

        # Check that hash is correct
        if "hash" not in group:
            return f"Missing required input 'hash' under 'settings.models.{label}'."
        if not isinstance(group["hash"], Str):
            return f"'settings.models.{label}.hash' must be of type Str, got {type(group['hash']).__name__}."
        if "hash_algorithm" in group:
            if not isinstance(group["hash_algorithm"], Str):
                return (
                    f"'settings.models.{label}.hash_algorithm' must by of type Str, got "
                    f"{type(group['hash_algorithm']).__name__}."
                )
            hash_algorithm = group["hash_algorithm"].value
        else:
            hash_algorithm = "sha3_256"
        if hash_algorithm not in hashlib.algorithms_guaranteed:
            return (
                f"'settings.models.{label}.hash_algorithm' must be a hash type which appears in "
                "hashlib.algorithms_guaranteed."
            )
        with open(path, "rb") as f:
            digest = hashlib.file_digest(f, hash_algorithm)
        if not group["hash"].value == digest.hexdigest():
            return f"'settings.models.{label}.hash' does not match {hash_algorithm} digest of file {path!s}."

        # If section is present, validate type
        if "section" in group:
            if not isinstance(group["section"], Str):
                return f"'settings.models.{label}.section' must be of type Str, got {type(group['section']).__name}."
