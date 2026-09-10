import hashlib
import pickle
from pathlib import Path

from aiida import load_profile
from aiida.engine import run
from aiida.orm import Dict, Str, load_code

from charlib.characterizer.characterizer import unit_registry
from charlib.characterizer.port import Direction, Role, Trigger
from charlib.characterizer.procedures.pin_capacitance.frequency_sweep import PinCapacitanceImpedanceDividerProcedure
from charlib.characterizer.procedures.utils import QuantityData


def test_pin_cap_impedance_divider():
    """Test the PinCapacitanceImpedanceDividerProcedure workchain with a known-capacitance example"""
    load_profile()
    spice_code = load_code(label="ngspice@localhost")
    cell_path = Path.cwd() / "test/characterizer/procedures/rc_circuit.spice"
    with open(cell_path, "rb") as f:
        digest = hashlib.file_digest(f, "sha3_256")
    cell_hash = digest.hexdigest()

    inputs = {
        "cell": {
            "name": "rc_circuit",
            "netlist": {
                "path": Str(cell_path),
                "hash": Str(cell_hash),
            },
            "functions": Dict(
                dict={
                    "OUT": "IN",
                }
            ),
            "ports": Dict(
                dict={
                    "OUT": {
                        "role": Role.LOGIC,
                        "direction": Direction.OUT,
                        "trigger": Trigger.LEVEL,
                    },
                    "IN": {
                        "role": Role.LOGIC,
                        "direction": Direction.IN,
                        "trigger": Trigger.LEVEL,
                    },
                    "VGND": {
                        "role": Role.GROUND,
                        "direction": Direction.IN,
                        "trigger": Trigger.LEVEL,
                    },
                }
            ),
        },
        "settings": {
            "simulation": {
                "engine": spice_code,
                "temperature": QuantityData(unit_registry.Quantity(25, unit_registry.degC)),
            },
            "units": {
                "time": "s",
                "voltage": "V",
                "current": "mA",
                "resistance": "ohm",
                "capacitance": "pF",
                "power": "nW",
                "energy": "J",
            },
            "logic_thresholds": {
                "high": 0.8,
                "low": 0.2,
                "rise": 0.5,
                "fall": 0.5,
            },
            "named_nodes": {
                "power": {
                    "name": "VDD",
                    "voltage": QuantityData(3 * unit_registry.volt),
                },
                "ground": {
                    "name": "VGND",
                    "voltage": QuantityData(0 * unit_registry.volt),
                },
                "nwell": {
                    "name": "VNW",
                    "voltage": QuantityData(3 * unit_registry.volt),
                },
                "pwell": {
                    "name": "VPW",
                    "voltage": QuantityData(0 * unit_registry.volt),
                },
            },
        },
        "parameters": {
            "in_cap": {
                "frequency": {
                    "min": QuantityData(1e4 * unit_registry.Hz),
                    "max": QuantityData(1e9 * unit_registry.Hz),
                },
                "voltage": QuantityData(2 * unit_registry.volt),
                "resistance": {
                    "series": QuantityData(1e3 * unit_registry.ohm),
                    "shunt": QuantityData(1e10 * unit_registry.ohm),
                },
            },
        },
    }

    results = run(PinCapacitanceImpedanceDividerProcedure, **inputs)
    assert results["liberty"] is not None

    with results["liberty"].open(mode="rb") as stream:
        cell_group = pickle.load(stream)

    print(cell_group.to_liberty(precision=6))
    assert cell_group is not None

    assert abs(cell_group.group("pin", "IN").attributes["capacitance"].value - 100) < 1e-6
