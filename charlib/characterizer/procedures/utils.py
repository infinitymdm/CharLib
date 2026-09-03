import logging
import re

from aiida.common.extendeddicts import AttributeDict
from aiida.engine import calcfunction
from aiida.orm import FolderData, List, SinglefileData, Str
from aiida_spice.utils.include_paths import get_include_paths

logger = logging.getLogger(__name__)


@calcfunction
def read_pins_in_netlist_order(cell_name: Str, cell_netlist: SinglefileData) -> List:
    """Read the subckt line for this cell and extract all items after the cell name."""
    subckt_pattern = re.compile(rf"^\s*\.subckt\s+{re.escape(cell_name.value)}\b", re.IGNORECASE)
    with cell_netlist.open(mode="r") as cell_spice:
        for line in cell_spice:
            if subckt_pattern.match(line):
                # FIXME: Handle params, pins split across lines, and other edge cases
                return List(list=line.split()[2:])
    logger.warning(f"No .subckt line found for cell {cell_name.value}")
    return List(list=[])


@calcfunction
def setup_netlist_includes(cell_netlist: SinglefileData, model_file: SinglefileData, model_lib: Str = None) -> List:
    """Write .include or .lib directive for cell subcircuits and transistor models in a cell"""
    netlist = []
    with cell_netlist.as_path() as cell_path:
        netlist.append(f".include {cell_path}")
    with model_file.as_path() as model_path:
        if model_lib is not None:
            netlist.append(f".lib {model_path} {model_lib.value}")
        else:
            netlist.append(f".include {model_path}")
    return List(list=netlist)


@calcfunction
def setup_netlist_supplies(named_nodes: AttributeDict) -> List:
    """Set up static named node voltage supplies for this netlist"""
    netlist = [
        f"Vpower {named_nodes.power.name.value} 0 {named_nodes.power.voltage.value}",
        f"Vpwell {named_nodes.pwell.name.value} 0 {named_nodes.pwell.voltage.value}",
        f"Vnwell {named_nodes.nwell.name.value} 0 {named_nodes.nwell.voltage.value}",
    ]
    if named_nodes.ground.name.value.lower() not in ["gnd", "0"]:
        # FIXME: Make sure this check is actually necessary for all simulators
        netlist.append(f"vground {named_nodes.ground.name.value} 0 {named_nodes.voltage.value}")
    return List(list=netlist)


@calcfunction
def read_includes_from_netlist(netlist: SinglefileData):
    includes = FolderData()
    with netlist.as_path() as netlist_path:
        for include_file in get_include_paths(netlist_path):
            includes.put_object_from_file(include_file, path=include_file.name)
    return includes
