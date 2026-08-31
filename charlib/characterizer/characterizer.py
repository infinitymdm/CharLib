"""Dispatches characterization jobs and manages cell data"""

from dataclasses import dataclass
from pathlib import Path

from charlib.characterizer.cell import Cell
from charlib.characterizer.units import UnitsSettings
from charlib.liberty.library import Library


class Characterizer:
    """Main object of Charlib. Keeps track of settings and cells, and schedules simulations."""

    def __init__(self, **kwargs) -> None:
        self.settings = CharacterizationSettings(**kwargs)
        self.library = Library(kwargs.pop("lib_name"), **self.settings.liberty_attrs_as_dict())
        self.cell_configs = []

    def add_cell(self, name: str, properties: dict):
        """Add a cell to be characterized"""
        # Get pg_pins from library settings, then construct the cell
        supply_pins = {
            self.settings.primary_power.name: "primary_power",
            self.settings.primary_ground.name: "primary_ground",
            self.settings.pwell.name: "pwell",
            self.settings.nwell.name: "nwell",
        }
        try:
            cell = Cell(name, supply_pins, **properties)
        except Exception as e:  # FIXME: We should have a more specific error type than this!
            if self.settings.omit_on_failure:
                return
            else:
                raise ValueError(f"Unable to add cell {name}") from e

        # Handle keywords for plots
        if properties.get("plots", []) == "all":
            properties["plots"] = ["delay", "io"]

        self.cell_configs.append((cell, self.settings, properties))

    def analyse_cell(self, cell) -> list:
        """Return a list of characterization tasks required for this cell."""
        pass  # TODO

    def characterize(self):
        """Execute scheduled simulation jobs in parallel"""
        # Setup: analyse cells and prepare workgraph
        # TODO

        # Execute workgraph
        # TODO

        # Post-processing: Fetch generated table templates and add them to the library
        lut_templates = []
        for timing_group in self.library.subgroups_with_name("timing"):
            lut_templates += [lut_group.template for lut_group in timing_group.groups.values()]
        [self.library.add_group(lut_template) for lut_template in lut_templates]

        return self.library.to_liberty(precision=6)


class CharacterizationSettings:
    """Container for characterization settings"""

    def __init__(self, **kwargs):
        """Create a new CharacterizationSettings instance"""
        # Behavioral settings
        self.jobs = None if kwargs.pop("multithreaded", True) else 1
        self.results_dir = Path(kwargs.pop("results_dir", "results"))
        self.plots_dir = self.results_dir / "plots"
        self.debug = kwargs.pop("debug", False)
        self.debug_dir = Path(kwargs.pop("debug_dir", "debug"))
        self.quiet = kwargs.pop("quiet", False)
        self.dry_run = kwargs.pop("dry_run", False)
        self.omit_on_failure = kwargs.get("omit_on_failure", False)
        self.cell_defaults = kwargs.get("cell_defaults", {})

        # Simulation procedures
        self.simulation = SimulationSettings(**kwargs.get("simulation", {}))

        # Units for simulation and results
        self.units = UnitsSettings(**kwargs.get("units", {}))

        # Library-wide named voltages
        nodes = kwargs.pop("named_nodes", {})
        self.primary_power = NamedNode(**nodes.get("primary_power", {"name": "VDD", "voltage": 3.3}))
        self.primary_ground = NamedNode(**nodes.get("primary_ground", {"name": "VSS", "voltage": 0}))
        self.pwell = NamedNode(**nodes.get("pwell", {"name": "VPW", "voltage": 0}))
        self.nwell = NamedNode(**nodes.get("nwell", {"name": "VNW", "voltage": 3.3}))

        # Logic thresholds
        self.logic_thresholds = LogicThresholds(**kwargs.get("logic_thresholds", {}))

        # Operating conditions
        self.temperature = kwargs.get("temperature", 25.0)

    @property
    def named_nodes(self):
        """Convenience accessor returning a tuple of all named nodes"""
        return (self.primary_power, self.primary_ground, self.nwell, self.pwell)

    def liberty_attrs_as_dict(self):
        """Return a dict of library-wide settings that should be written to the liberty file."""

        def spice_unit(unit):
            return f"1{unit:~P}"

        return {
            "nom_voltage": self.primary_power.voltage,
            "nom_temperature": self.temperature,
            "time_unit": spice_unit(self.units.time),
            "voltage_unit": spice_unit(self.units.voltage),
            "current_unit": spice_unit(self.units.current),
            "pulling_resistance_unit": spice_unit(self.units.current),
            "leakage_power_unit": spice_unit(self.units.power),
            "capacitive_load_unit": spice_unit(self.units.capacitance),
            "slew_upper_threshold_pct_rise": self.logic_thresholds.high,
            "slew_lower_threshold_pct_rise": self.logic_thresholds.low,
            "slew_upper_threshold_pct_fall": self.logic_thresholds.high,
            "slew_lower_threshold_pct_fall": self.logic_thresholds.low,
            "input_threshold_pct_rise": self.logic_thresholds.rising,
            "input_threshold_pct_fall": self.logic_thresholds.falling,
            "output_threshold_pct_rise": self.logic_thresholds.rising,
            "output_threshold_pct_fall": self.logic_thresholds.falling,
        }


@dataclass
class SimulationSettings:
    """Container for simulation backend and procedures"""

    backend: str = "ngspice"
    procedures: tuple[str] = (
        "input_capacitance_by_charge_integration",
        "average_combinational_delay",
        "sequential_delay_by_c2q_contour",
        "static_leakage_power",
    )


@dataclass
class LogicThresholds:
    """Describes logic thresholds as fractions of primary power voltage"""

    low: float = 0.2
    high: float = 0.8
    rising: float = 0.5
    falling: float = 0.5


@dataclass
class NamedNode:
    """Binds supply node names to voltages"""

    name: str
    voltage: float = 0

    def __str__(self) -> str:
        return f"Name: {self.name}\nVoltage: {self.voltage}"

    def __repr__(self) -> str:
        return f"NamedNode({self.name}, {self.voltage})"

    @property
    def subscript(self) -> str:
        """Return the 'subscript' portion of the voltage name e.g. Vdd -> dd"""
        return self.name[1:] if self.name.lower().startswith("v") else self.name
