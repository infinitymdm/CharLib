from charlib.characterizer import utils
from charlib.characterizer.cell import Port
from charlib.characterizer.procedures import Procedure, SimulationNode, SimulationResult, Variation
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
    def is_applicable(cls, config) -> bool:
        """Verify the cell has input pins and the config has the required parameters"""
        has_inputs = config.cell.filter_pins(direction='input', role=cls._target_pin_roles())
        has_params = set(cls.params()).issubset(config.config.parameters)
        return has_inputs and has_params

    @classmethod
    def generate_dag(cls, config) -> Set[SimulationNode]:
        for target_pin in config.cell.filter_pins(direction='input', role=cls._target_pin_roles()):
            # Final result will be aggregated from many simulations
            aggregator_criterion = config.config.parameters.get('in_cap_selection_criterion').lower()
            if aggregator_criterion == 'max':
                aggregator_node = MaxNode()
            else:
                aggregator_node = MeanNode()

            # Generate simulation nodes
            for config_conditions in cls.vary_config_params(config.config):
                variation = Variation(frozenset([('target_pin', target_pin), *config_conditions]))
                work_dir = config.settings.work_dir / config.cell.name / cls.__name__ / variation.to_path_slug()
                sim_node = InputCapacitanceFrequencySweepNode(variation, work_dir)
                aggregator_node.add_dependency(sim_node)

            # Yield each terminal node
            yield aggregator_node


class InputCapacitanceFrequencySweepNode(SimulationNode):
    """Stimulate an input pin with a constant-amplitude AC current chirp to measure capacitance.

    Modeling the cell as a grounded capacitor, perform an AC frequency sweep and measure voltage.
    Compute capacitance as d/ds(i(s)/v(s)).
    """

    def _run_simulation(self, dependency_results) -> SimulationResult:
        cell = self.config.cell
        config = self.config.config
        settings = self.config.settings

        conditions = dict(zip(self.variation.conditions))
        f_start = conditions['in_cap_start_frequency'] @ PySpice.Unit.u_Hz
        f_stop = conditions['in_cap_end_frequency'] @ PySpice.Unit.u_Hz
        r_shunt = conditions['in_cap_shunt_resistance'] * settings.units.resistance
        i_in = conditions['in_cap_current_amplitude'] * settings.units.current

        # Build the circuit
        circuit = utils.init_circuit(self.variation.to_path_slug(), cell.netlist, config.models, settings.named_nodes, settings.units)
        circuit.I('in', circuit.gnd, 'vin', f'DC 0 AC {PySpice.Spice.unit.str_spice(i_in)}')
        connections = []
        for pin in cell.pins_in_netlist_order():
            match pin.role:
                case Port.Role.POWER:
                    connections.append(settings.primary_power.name)
                case Port.Role.GROUND:
                    connections.append(settings.primary_ground.name)
                case Port.Role.NWELL:
                    connections.append(settings.nwell.name)
                case Port.Role.PWELL:
                    connections.append(settings.pwell.name)
                case _: # Any other role (logic, clock, analog, clear, enable, set, or preset)
                    if pin.name == conditions['target_pin']:
                        connections.append('vin')
                    else:
                        # Add a shunt resistor to each other pin
                        circuit.R(pin.name, f'v{pin.name}', circuit.gnd, r_shunt)
                        connections.append(f'v{pin.name}')
        circuit.X('dut', cell.name, *connections)

        simulator = PySpice.Simulator.factory(simulator=settings.simulation.backend)
        simulation = simulator.simulation(circuit, temperature=settings.temperature)
        simulation.ac('dec', 100, f_start, f_stop, run=False)

        if settings.debug:
            debug_path = settings.debug_dir / cell.name / __name__.split('.')[-1]
            debug_path.mkdir(parents=True, exist_ok=True)
            with open(debug_path/f'{conditions["target_pin"]}.spice', 'w') as spice_file:
                spice_file.write(str(simulation))

        analysis = simulator.run(simulation)
        conductance = np.reciprocal(np.abs(analysis.vin)/i_in)
        [*_, capacitance] = np.polynomial.polynomial.polyfit(analysis.frequency, conductance, 1)
        converted_cap = (capacitance @ PySpice.Unit.u_F).convert(settings.units.capacitance.prefixed_unit).value

        return SimulationResult(self.variation, {'capacitance': converted_cap}, capacitance > 0)
