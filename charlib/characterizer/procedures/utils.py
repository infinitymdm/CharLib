import hashlib
import logging
import re
from pathlib import Path

from aiida.engine import calcfunction
from aiida.orm import Data, Dict, List, SinglefileData, Str

from charlib.characterizer.characterizer import unit_registry
from charlib.characterizer.port import Role

logger = logging.getLogger(__name__)


class QuantityData(Data):
    """AiiDA custom data node storing physical quantities with units."""

    def __init__(self, quantity=None, **kwargs):
        super().__init__(**kwargs)
        if quantity is not None:
            self.set_quantity(quantity)

    def set_quantity(self, quantity):
        """Save magnitude and unit as attributes."""
        if not isinstance(quantity, unit_registry.Quantity):
            raise TypeError("Input must be a pint.Quantity object.")
        self.base.attributes.set("value", quantity.magnitude)
        self.base.attributes.set("units", str(quantity.units))

    @property
    def quantity(self):
        """Reconstruct and return the pint.Quantity object."""
        value = self.base.attributes.get("value")
        units = self.base.attributes.get("units")
        return unit_registry.Quantity(value, units)


def voltage_supply(name: str, voltage: float | str, cathode_node: str = "", anode_node: str = "") -> str:
    """Construct a string representing a voltage source spice definition"""
    if not cathode_node:
        cathode_node = name
    if not anode_node:
        anode_node = "0"
    return f"V{name} {cathode_node} {anode_node} {voltage}"


def resistor(name: str, resistance: float | str, node_1: str, node_2: str) -> str:
    """Construct a string representing a resistor spice definition"""
    return f"R{name} {node_1} {node_2} {resistance}"


def subcircuit(name: str, subcircuit: str, *connections: list[str]) -> str:
    """Construct a string representing a spice subcircuit instantiation"""
    return f"X{name} {' '.join(connections)} {subcircuit}"


@calcfunction
def create_include_statement(path: Str) -> List:
    return List(list=[f".include {path.value}"])


@calcfunction
def create_lib_statement(path: Str, section: Str | None = None) -> List:
    return List(list=f".lib {path.value} {section.value}")


@calcfunction
def create_vpower(name: Str, voltage: QuantityData) -> List:
    supply = voltage_supply("power", voltage.quantity.to("volts").magnitude, cathode_node=name.value)
    return List(list=[supply])


@calcfunction
def create_vground(name: Str, voltage: QuantityData) -> List:
    if name.value not in ["gnd", "0"]:
        supply = voltage_supply("ground", voltage.quantity.to("volts").magnitude, cathode_node=name.value)
    else:
        supply = f"* Omitted ground node with name {name.value}"
    return List(list=[supply])


@calcfunction
def create_vpwell(name: Str, voltage: QuantityData) -> List:
    supply = voltage_supply("pwell", voltage.quantity.to("volts").magnitude, cathode_node=name.value)
    return List(list=[supply])


@calcfunction
def create_vnwell(name: Str, voltage: QuantityData) -> List:
    supply = voltage_supply("nwell", voltage.quantity.to("volts").magnitude, cathode_node=name.value)
    return List(list=[supply])


@calcfunction
def combine_lists(*args: List):
    """Combine any number of lists into a single list"""
    combined = []
    for list_node in args:
        combined += list_node.get_list()
    return List(list=combined)


@calcfunction
def read_pins_in_netlist_order(cell_name: Str, cell_netlist_path: Str) -> List:
    """Read the subckt line for this cell and extract all items after the cell name."""
    subckt_pattern = re.compile(rf"^\s*\.subckt\s+{re.escape(cell_name.value)}\b", re.IGNORECASE)
    with open(Path(cell_netlist_path.value), "r") as cell_spice:
        for line in cell_spice:
            if subckt_pattern.match(line):
                # FIXME: Handle params, pins split across lines, and other edge cases
                return List(list=line.split()[2:])
    logger.warning(f"No .subckt line found for cell {cell_name.value}")
    return List(list=[])


@calcfunction
def create_generic_subcircuit_connections(ports: Dict, ordered_pins: List, **node_names) -> List:
    """Create a list of pin names in the correct order for subcircuit wire-up"""
    subcircuit_connections = []
    for pin_name in ordered_pins.get_list():
        if pin_name not in ports.get_dict():
            logger.warning(f"Ignoring unexpected port: {pin_name}")
            continue
        match ports[pin_name].get("role", None):
            case Role.POWER:
                subcircuit_connections.append(node_names.get("power", "power"))
            case Role.GROUND:
                subcircuit_connections.append(node_names.get("ground", "ground"))
            case Role.NWELL:
                subcircuit_connections.append(node_names.get("nwell", "nwell"))
            case Role.PWELL:
                subcircuit_connections.append(node_names.get("pwell", "pwell"))
            case _:
                subcircuit_connections.append(pin_name)
    return List(list=subcircuit_connections)


@calcfunction
def create_generic_subcircuit(subcircuit_name, subcircuit_connections) -> List:
    return List(list=[subcircuit("dut", subcircuit_name.value, *subcircuit_connections.get_list())])


@calcfunction
def create_netlist_includes(cell_netlist: SinglefileData, model_file: SinglefileData, model_lib: Str = None) -> List:
    """Write .include or .lib directive for cell subcircuits and transistor models in a cell"""
    includes = []
    with cell_netlist.as_path() as cell_path:
        includes.append(f".include {cell_path}")
    with model_file.as_path() as model_path:
        if model_lib:
            includes.append(f".lib {model_path} {model_lib.value}")
        else:
            includes.append(f".include {model_path}")
    return List(list=includes)


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
                return f"'section' must be of type Str, got {type(group['section']).__name}."
        file_error = validate_files_with_hashes(group, port)
        if file_error is not None:
            return file_error
