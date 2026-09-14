import logging

from charlib.characterizer.procedures import CharacterizationProcedure
from charlib.characterizer.procedures.utils import QuantityData

logger = logging.getLogger(__name__)


class PinCapacitanceChargeIntegrationProcedure(CharacterizationProcedure):
    """Measure input capacitance for each input by integrating charge with respect to time.

    Treat the cell as a grounded capacitor with fixed capacitance. With all non-target pins in a high-impedance state,
    apply a rise or fall voltage waveform with the specified slew time. Each edge can be integrated to produce values
    for rise_capacitance and fall_capacitance liberty attributes respectively.

    This procedure is modified from the charge_integration procedure originally contributed by GitHub user
    e-dworkin.
    """

    @classmethod
    def define(cls, spec):
        super().define(spec)

        # Procedure-specific inputs
        spec.input(
            "parameters.in_cap.resistance.shunt",
            valid_type=QuantityData,
            help="Shunt resistance applied to all circuit nodes",
        )
        spec.input(
            "parameters.time.slew",
            valid_type=QuantityData,
            help=(
                "The amount of time the input voltage waveform should take to slew from settings.logic_thresholds.low "
                "to settings.logic_thresholds.high (and vice versa)"
            ),
        )

    def build_netlists(self):
        self.setup_initial_netlist()
        # TODO

    def run_simulations(self):
        pass  # TODO

    def write_liberty(self):
        pass  # TODO
