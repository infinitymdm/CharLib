"""Dispatches characterization jobs and manages cell data"""

from charlib.characterizer import plots
from charlib.characterizer.cell import Cell
from charlib.characterizer.units import UnitsSettings
from charlib.characterizer.procedures import CellConfig, Procedure
from charlib.orchestrator import Node, Orchestrator
from charlib.liberty.library import Library
from dataclasses import dataclass, field
import matplotlib.pyplot as plt
from pathlib import Path
# from tqdm import tqdm

from charlib.characterizer.procedures.pin_capacitance.frequency_sweep import InputCapacitanceFrequencySweep


class Characterizer:
    """Main object of Charlib. Keeps track of settings and cells, and schedules simulations."""

    def __init__(self, **kwargs) -> None:
        self.settings = CharacterizationSettings(**kwargs)
        self.library = Library(kwargs.pop('lib_name'), **self.settings.liberty_attrs_as_dict())
        self.cell_configs = []

    def add_cell(self, name: str, properties: dict):
        """Add a cell to be characterized"""
        # Get pg_pins from library settings, then construct the cell
        supply_pins = {self.settings.primary_power.name: 'primary_power',
                       self.settings.primary_ground.name: 'primary_ground',
                       self.settings.pwell.name: 'pwell',
                       self.settings.nwell.name: 'nwell'}
        try:
            cell = Cell(name, supply_pins, **properties)
        except Exception as e: # FIXME: We should have a more specific error type than this!
            if self.settings.omit_on_failure:
                return
            else:
                raise ValueError(f'Unable to add cell {name}: {e}') from e

        # Handle keywords for plots
        if properties.get('plots', []) == 'all':
            properties['plots'] = ['delay', 'io']

        # Add the cell
        self.cell_configs.append(CellConfig(cell, self.settings, properties))

    def analyse_cell(self, config: CellConfig) -> set[Node]:
        """Return characterization tasks for this cell."""
        procedures = filter(lambda p: p.is_applicable(config), self.settings.simulation.procedures)
        return set(*[p.generate_dag(config) for p in procedures])

    def characterize(self):
        """Execute scheduled simulation jobs in parallel"""
        # Setup: Prepare simulation jobs single-threadedly (is that a word?)
        nodes = set()
        for config in self.cell_configs:
            nodes |= self.analyse_cell(config)
        orchestrator = Orchestrator(nodes, self.settings.jobs)
        results = orchestrator.execute()
        [print(r, v) for r, v, in results.items()]

        # Post-processing: Fetch generated table templates and add them to the library
        lut_templates = []
        for timing_group in self.library.subgroups_with_name('timing'):
            lut_templates += [lut_group.template for lut_group in timing_group.groups.values()]
        [self.library.add_group(lut_template) for lut_template in lut_templates]

        # Plot delay surfaces (if desired)
        for (cell, config) in self.cells:
            cell_group = self.library.group('cell', cell.name)
            if 'delay' in config.plots:
                for pin_group in cell_group.subgroups_with_name('pin'):
                    pin = pin_group.identifier
                    for timing_group in pin_group.subgroups_with_name('timing'):
                        related_pin = timing_group.attributes['related_pin'].value
                        fig = plots.plot_delay_surfaces(list(timing_group.groups.values()),
                                                        title=f'Cell delays ({related_pin} to {pin})')
                        # FIXME: let user decide whether to show or save
                        fig_path = self.settings.plots_dir / cell.name
                        fig_path.mkdir(parents=True, exist_ok=True)
                        fig.savefig(fig_path / f'{related_pin} to {pin} delay.png') # FIXME: filetype should be configurable
                        plt.close()
        return self.library.to_liberty(precision=6)


class CharacterizationSettings:
    """Container for characterization settings"""
    def __init__(self, **kwargs):
        """Create a new CharacterizationSettings instance"""
        # Behavioral settings
        self.jobs = None if kwargs.pop('multithreaded', True) else 1
        self.debug = kwargs.pop('debug', False)
        self.debug_dir = Path(kwargs.pop('debug_dir', 'debug'))
        self.work_dir = Path(kwargs.pop('work_dir', 'work'))
        self.results_dir = Path(kwargs.pop('results_dir', 'results'))
        self.plots_dir = self.results_dir / 'plots'
        self.quiet = kwargs.pop('quiet', False)
        self.dry_run = kwargs.pop('dry_run', False)
        self.omit_on_failure = kwargs.get('omit_on_failure', False)
        self.cell_defaults = kwargs.get('cell_defaults', {})

        # Simulation procedures
        self.simulation = SimulationSettings(**kwargs.get('simulation', {}))

        # Units for simulation and results
        self.units = UnitsSettings(**kwargs.get('units', {}))

        # Library-wide named voltages
        nodes = kwargs.pop('named_nodes', {})
        self.primary_power = NamedVoltage(**nodes.get('primary_power', {'name':'VDD', 'voltage': 3.3}))
        self.primary_ground = NamedVoltage(**nodes.get('primary_ground', {'name':'VSS', 'voltage': 0}))
        self.pwell = NamedVoltage(**nodes.get('pwell', {'name':'VPW', 'voltage': 0}))
        self.nwell = NamedVoltage(**nodes.get('nwell', {'name':'VNW', 'voltage': 3.3}))

        # Logic thresholds
        self.logic_thresholds = LogicThresholds(**kwargs.get('logic_thresholds', {}))

        # Operating conditions
        self.temperature = kwargs.get('temperature', 25)

    @property
    def named_nodes(self):
        """Convenience accessor returning a tuple of all named nodes"""
        return (self.primary_power, self.primary_ground, self.nwell, self.pwell)

    def liberty_attrs_as_dict(self):
        """Return a dict of library-wide settings that should be written to the liberty file."""
        def spice_unit(unit):
            return f'1{unit.prefixed_unit.str_spice()}'
        return {
            'nom_voltage': self.primary_power.voltage,
            'nom_temperature': self.temperature,
            'time_unit': spice_unit(self.units.time),
            'voltage_unit': spice_unit(self.units.voltage),
            'current_unit': spice_unit(self.units.current),
            'pulling_resistance_unit': spice_unit(self.units.current),
            'leakage_power_unit': spice_unit(self.units.power),
            'capacitive_load_unit': [1, self.units.capacitance.prefixed_unit.str_spice()],
            'slew_upper_threshold_pct_rise': self.logic_thresholds.high,
            'slew_lower_threshold_pct_rise': self.logic_thresholds.low,
            'slew_upper_threshold_pct_fall': self.logic_thresholds.high,
            'slew_lower_threshold_pct_fall': self.logic_thresholds.low,
            'input_threshold_pct_rise': self.logic_thresholds.rising,
            'input_threshold_pct_fall': self.logic_thresholds.falling,
            'output_threshold_pct_rise': self.logic_thresholds.rising,
            'output_threshold_pct_fall': self.logic_thresholds.falling,
        }


@dataclass
class SimulationSettings:
    backend: str = 'ngspice-shared'
    procedures: list[str] = field(default_factory=list)

    def __post_init__(self):
        # Validate procedures
        for p in self.procedures:
            if p not in self.known_procedure_map():
                raise ValueError(f'Unrecognized procedure {p}')
        if not self.procedures:
            self.procedures = list(self.known_procedure_map().values())

    @classmethod
    def known_procedure_map(cls) -> dict[str, type[Procedure]]:
        """Return a list of known procedure types"""
        # TODO: search the current namespace for classes which satisfy issubclass(Procedure)
        # For now this is a static registry, effectively replacing the old register mechanism
        return {'InputCapacitanceFrequencySweep': InputCapacitanceFrequencySweep}


@dataclass
class LogicThresholds:
    low: float = 0.2
    high: float = 0.8
    rising: float = 0.5
    falling: float = 0.5


@dataclass
class NamedVoltage:
    name: str
    voltage: float

    @property
    def subscript(self) -> str:
        """Return the 'subscript' portion of the voltage name e.g. Vdd -> dd"""
        return self.name[1:] if self.name.lower().startswith('v') else self.name
