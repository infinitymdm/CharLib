import re
from abc import abstractmethod

import pint
from aiida.engine import WorkChain
from aiida.orm import Data, Dict, Float, SinglefileData, Str

ureg = pint.UnitRegistry()


class CharacterizationProcedure(WorkChain):
    """Abstract base class for all characterization Procedures"""

    @classmethod
    def define(cls, spec):
        """Specify common inputs and outputs. Subclasses will likely define additional I/O."""
        super().define(spec)

        # Cell
        spec.input("cell.name", valid_type=Str, help="Cell name as it appears in the netlist")
        spec.input("cell.netlist", valid_type=StandardCellData, help="The spice netlist for the cell")
        spec.input("cell.functions", valid_type=Dict, help="Boolean functions for each cell output")
        spec.input("cell.ports", valid_type=Dict, help="Port names and metadata")

        # Simulation
        spec.input(
            "settings.simulation.model.file", valid_type=SinglefileData, help="Transistor models used in cell netlist"
        )
        spec.input(
            "settings.simulation.model.lib",
            valid_type=Str,
            required=False,
            help="Which section of the model file to import with a .lib directive",
        )
        spec.input("settings.simulation.temperature", valid_type=Float)

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
        spec.input("settings.named_nodes.power.voltage", valid_type=Float)
        spec.input("settings.named_nodes.ground.name", valid_type=Str)
        spec.input("settings.named_nodes.ground.voltage", valid_type=Float)
        spec.input("settings.named_nodes.pwell.name", valid_type=Str)
        spec.input("settings.named_nodes.pwell.voltage", valid_type=Float)
        spec.input("settings.named_nodes.nwell.name", valid_type=Str)
        spec.input("settings.named_nodes.nwell.voltage", valid_type=Float)

        # Subclasses must define outline

        # Output a pickled liberty cell group
        spec.output(
            "liberty",
            valid_type=SinglefileData,
            help="A pickled liberty cell group annotated with this procedure's results.",
        )

    def setup_supplies(self, netlist: list[str]):
        """Set up static named node voltage supplies for this netlist"""
        netlist.extend(
            [
                f"Vpower {self.inputs.settings.named_nodes.power.name.value} 0 {self.inputs.settings.named_nodes.power.voltage.value}",
                f"Vpwell {self.inputs.settings.named_nodes.pwell.name.value} 0 {self.inputs.settings.named_nodes.pwell.voltage.value}",
                f"Vnwell {self.inputs.settings.named_nodes.nwell.name.value} 0 {self.inputs.settings.named_nodes.nwell.voltage.value}",
            ]
        )
        if self.settings.named_nodes.ground.name.value.lower() not in ["gnd", "0"]:
            # FIXME: Make sure this check is actually necessary for all simulators
            netlist.append(
                f"vground {self.inputs.settings.named_nodes.ground.name.value} 0 {self.inputs.settings.named_nodes.voltage.value}"
            )
        return netlist

    def get_subckt_line(self):
        """Read the subckt line for this cell from the cell netlist"""
        subckt_pattern = re.compile(rf"^\s*\.subckt\s+{re.escape(self.name)}\b", re.IGNORECASE)
        with self.inputs.cell.netlist.open(mode="r") as cell_netlist:
            for line in cell_netlist:
                if subckt_pattern.match(line):
                    return line


class QuantityData(Data):
    """AiiDA custom data node storing physical quantities with units."""

    def __init__(self, quantity=None, **kwargs):
        super().__init__(**kwargs)
        if quantity is not None:
            self.set_quantity(quantity)

    def set_quantity(self, quantity):
        """Save magnitude and unit as attributes."""
        if not isinstance(quantity, ureg.Quantity):
            raise TypeError("Input must be a pint.Quantity object.")
        self.base.attributes.set("value", quantity.magnitude)
        self.base.attributes.set("units", str(quantity.units))

    @property
    def quantity(self):
        """Reconstruct and return the pint.Quantity object."""
        value = self.base.attributes.get("value")
        units = self.base.attributes.get("units")
        return value * ureg(units)
