from charlib.characterizer import utils
from charlib.characterizer.cell import Port
from charlib.characterizer.procedures import Procedure, CellConfig, SimulationNode, SimulationResult, Variation
from charlib.characterizer.procedures.aggregators import MaxNode, MeanNode
import numpy as np
import PySpice
from typing import List, Set

class InputCapacitanceFrequencySweep(Procedure):
    """Measure input pin capacitance by performing an AC frequency sweep"""

    @classmethod
    def variation_params(cls) -> list:
        return []

    @classmethod
    def runtime_params(cls) -> list:
        return [
            'in_cap_start_frequency',
            'in_cap_end_frequency',
            'in_cap_shunt_resistance',
            'in_cap_current_amplitude',
            'in_cap_selection_criterion',
        ]

    @classmethod
    def _target_pin_roles(cls) -> List[str]:
        return ['logic', 'clock', 'analog', 'reset', 'set', 'enable']

    @classmethod
    def is_applicable(cls, config: CellConfig) -> bool:
        """Verify the cell has input pins and the config has the required parameters"""
        has_inputs = list(config.cell.filter_pins(direction='input', role=cls._target_pin_roles()))
        has_params = set(cls.params()).issubset(config.parameters)
        return has_inputs and has_params

    @classmethod
    def generate_dag(cls, config) -> Set[SimulationNode]:
        for target_pin in config.cell.filter_pins(direction='input', role=cls._target_pin_roles()):
            # Final result will be aggregated from many simulations
            aggregator_criterion = config.parameters.get('in_cap_selection_criterion').lower()
            aggregator_variation = Variation(frozenset([
                    ('cell', config.cell.name),
                    ('target_pin', target_pin.name)
            ]))
            work_dir = config.settings.work_dir / config.cell.name / cls.__name__
            aggregator_dir = work_dir / aggregator_variation.to_path_slug()
            if aggregator_criterion == 'max':
                aggregator_node = MaxNode(config, aggregator_variation, aggregator_dir)
            else:
                aggregator_node = MeanNode(config, aggregator_variation, aggregator_dir)

            # Generate simulation nodes
            for config_conditions in cls.vary_config_params(config):
                variation = Variation(frozenset([
                    ('cell', config.cell.name),
                    ('target_pin', target_pin.name),
                    *config_conditions
                ]))
                sim_node = InputCapacitanceFrequencySweepNode(config, variation, work_dir / variation.to_path_slug())
                aggregator_node.add_dependency(sim_node)

            # Yield each terminal node
            yield aggregator_node


class InputCapacitanceFrequencySweepNode(SimulationNode):
    """Stimulate an input pin with a constant-amplitude AC current chirp to measure capacitance.

    Modeling the cell as a grounded capacitor, perform an AC frequency sweep and measure voltage.
    Compute capacitance as d/ds(i(s)/v(s)).
    """

    def _run_simulation(self, dependency_results) -> SimulationResult:
        conditions = dict(self.variation.conditions)
        f_start = conditions['in_cap_start_frequency'] @ PySpice.Unit.u_Hz
        f_stop = conditions['in_cap_end_frequency'] @ PySpice.Unit.u_Hz
        r_shunt = conditions['in_cap_shunt_resistance'] * self.config.settings.units.resistance
        i_in = conditions['in_cap_current_amplitude'] * self.config.settings.units.current

        # Build the circuit
        circuit = utils.init_circuit(self.variation.to_path_slug(), self.config.cell.netlist,
                self.config.cell.models, self.config.settings.named_nodes,
                self.config.settings.units)
        circuit.I('in', circuit.gnd, 'vin', f'DC 0 AC {PySpice.Spice.unit.str_spice(i_in)}')
        connections = []
        for pin in self.config.cell.pins_in_netlist_order():
            match pin.role:
                case Port.Role.POWER:
                    connections.append(self.config.settings.primary_power.name)
                case Port.Role.GROUND:
                    connections.append(self.config.settings.primary_ground.name)
                case Port.Role.NWELL:
                    connections.append(self.config.settings.nwell.name)
                case Port.Role.PWELL:
                    connections.append(self.config.settings.pwell.name)
                case _: # Any other role (logic, clock, analog, clear, enable, set, or preset)
                    if pin.name == conditions['target_pin']:
                        connections.append('vin')
                    else:
                        # Add a shunt resistor to each other pin
                        circuit.R(pin.name, f'v{pin.name}', circuit.gnd, r_shunt)
                        connections.append(f'v{pin.name}')
        circuit.X('dut', self.config.cell.name, *connections)

        simulator = PySpice.Simulator.factory(simulator=self.config.settings.simulation.backend)
        simulation = simulator.simulation(circuit, temperature=self.config.settings.temperature)
        simulation.ac('dec', 100, f_start, f_stop, run=False)

        if self.config.settings.debug:
            debug_path = self.config.settings.debug_dir / self.config.cell.name / __name__.split('.')[-1]
            debug_path.mkdir(parents=True, exist_ok=True)
            with open(debug_path/f'{conditions["target_pin"]}.spice', 'w') as spice_file:
                spice_file.write(str(simulation))

        analysis = simulator.run(simulation)
        conductance = np.reciprocal(np.abs(analysis.vin)/i_in)
        [*_, capacitance] = np.polynomial.polynomial.polyfit(analysis.frequency, conductance, 1)
        converted_cap = (capacitance @ PySpice.Unit.u_F).convert(self.config.settings.units.capacitance.prefixed_unit).value

        return SimulationResult(self.variation, {'capacitance': converted_cap}, capacitance > 0)
