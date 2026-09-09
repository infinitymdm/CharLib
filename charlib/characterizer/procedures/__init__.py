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
        spec.input("settings.model.file", valid_type=SinglefileData, help="Transistor models used in cell netlist")
        spec.input(
            "settings.model.lib",
            valid_type=Str,
            required=False,
            help="The section of the model file to import with a .lib directive",
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
        1. Initilize voltage supplies from settings.named_nodes
        """
        named_nodes = self.inputs.settings.named_nodes
        supplies = [
            utils.create_vpower(named_nodes.power.name, named_nodes.power.voltage),
            utils.create_vground(named_nodes.ground.name, named_nodes.ground.voltage),
            utils.create_vpwell(named_nodes.pwell.name, named_nodes.pwell.voltage),
            utils.create_vnwell(named_nodes.nwell.name, named_nodes.nwell.voltage),
        ]
        self.ctx.initial_netlist = utils.combine_lists(*supplies)
