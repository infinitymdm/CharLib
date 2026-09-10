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
        spec.input_namespace(
            "cell.netlist",
            dynamic=True,
            validator=validate_files_with_hashes,
            help="A netlist containing the subcircuit definition defining the cell's spice model.",
        )
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
        2. Add an include statement for the cell netlist
        3. Initilize voltage supplies from settings.named_nodes
        """
        # Add model imports
        model_imports = []
        if "models" in self.inputs.settings:
            for model in self.inputs.settings.models.values:
                if "section" in model:
                    model_imports.append(utils.create_lib_statement(model.path, model.section))
                else:
                    model_imports.append(utils.create_include_statement(model.path))

        # Add cell netlist import
        cell_import = utils.create_include_statement(self.inputs.cell.netlist.path)

        # Build voltage supplies
        named_nodes = self.inputs.settings.named_nodes
        supplies = [
            utils.create_vpower(named_nodes.power.name, named_nodes.power.voltage),
            utils.create_vground(named_nodes.ground.name, named_nodes.ground.voltage),
            utils.create_vpwell(named_nodes.pwell.name, named_nodes.pwell.voltage),
            utils.create_vnwell(named_nodes.nwell.name, named_nodes.nwell.voltage),
        ]
        self.ctx.initial_netlist = utils.combine_lists(*model_imports, cell_import, *supplies)


def validate_files_with_hashes(value, port):  # noqa: PLR0911
    """Validate inputs to namespaces expecting files with accompanying hashes.

    Each valid entry has the following items:
    - 'path': a valid path Str which points to an extant file
    - 'hash': a Str which matches the hexadecimal hash of the file at 'path'
    - 'hash_algorithm': an optional Str specifying hash algorithm used to generate 'hash'. Defaults to sha3_256.
    """
    # Check that path exists
    if "path" not in value:
        return "Missing required input 'path'."
    if not isinstance(value["path"], Str):
        return f"'path' must be of type Str, got {type(value['path']).__name__}."
    path = Path(value["path"].value).resolve()
    if not path.is_file():
        return "'path' does not contain a path to an extant file."

    # Check that hash is correct
    if "hash" not in value:
        return "Missing required input 'hash'."
    if not isinstance(value["hash"], Str):
        return f"'hash' must be of type Str, got {type(value['hash']).__name__}."
    if "hash_algorithm" in value:
        if not isinstance(value["hash_algorithm"], Str):
            return f"'hash_algorithm' must by of type Str, got {type(value['hash_algorithm']).__name__}."
        hash_algorithm = value["hash_algorithm"].value
    else:
        hash_algorithm = "sha3_256"
    if hash_algorithm not in hashlib.algorithms_guaranteed:
        return "'hash_algorithm' must be a hash type which appears in hashlib.algorithms_guaranteed."
    with open(path, "rb") as f:
        digest = hashlib.file_digest(f, hash_algorithm)
    if not value["hash"].value == digest.hexdigest():
        return f"'hash' does not match {hash_algorithm} digest of file {path!s}."


def validate_models(value, port):
    """Validate inputs to the models namespace.

    Each valid models entry is identical to a netlist entry, with one additional optional parameter:
    - 'section': an optional Str. If provided, imports use ".lib <path> <section>."; otherwise ".inc <path>".
    """
    for label, group in value.items():
        # If section is present, validate type
        if "section" in group:
            if not isinstance(group["section"], Str):
                return f"'settings.models.{label}.section' must be of type Str, got {type(group['section']).__name}."
        file_error = validate_files_with_hashes(group, port)
        if file_error is not None:
            return file_error
