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
        spec.input("cell.netlist", valid_type=SinglefileData, help="The spice netlist for the cell")
        spec.input("cell.functions", valid_type=Dict, help="Boolean functions for each cell output")
        spec.input("cell.ports", valid_type=Dict, help="Port names and metadata")

        # Simulation settings
        spec.input("settings.model.file", valid_type=SinglefileData, help="Transistor models used in cell netlist")
        spec.input(
            "settings.model.lib",
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
