"""Encapsulates a cell's external interfaces"""

from dataclasses import dataclass
from enum import Flag, StrEnum


class Direction(StrEnum):
    """Enumerate valid port directions

    Port direction describes whether the cell drives the port or expects the port to be driven
    by an external actor."""

    IN = "input"
    OUT = "output"
    INOUT = "inout"


class Role(StrEnum):
    """Enumerate valid port roles

    A port's role describes how it is to be used during characterization. Most ports are simple
    logic I/Os, but some ports, such as clocks and resets, have special roles that require
    a different approach to timing characterization. These are also useful for constructing the
    liberty file after characterization.
    """

    LOGIC = "logic"  # Normal inputs and outputs
    CLOCK = "clock"
    ANALOG = "analog"
    POWER = "primary_power"
    GROUND = "primary_ground"
    PWELL = "pwell"
    NWELL = "nwell"
    CLEAR = "reset"
    PRESET = "set"
    ENABLE = "enable"  # Tristate enable


class Trigger(Flag):
    """Enumerate how we expect an input to be stimulated, or how an output should respond.

    This field describes how a values in a truth table or test vector ate to be interpreted
    and applied as stimulus or measured as output.

    Most pins are level-triggered, meaning they are sensitive to either logical 1 or logical 0.
    These pins should be stimulated with static high- or low-voltage signals. Edge-sensitive
    pins, on the other hand, should be stimulated with rising or falling signals.

    Applying this to truth tables and test vectors:
    - For level-triggered pins, 0 corresponds to low voltage and 1 corresponds to high voltage.
    - For edge-triggered pins, 0 corresponds to a "fall" (slewing from 1 to 0) and 1
        corresponds to a "rise" (slewing from 0 to 1).
    This means that a 01 in a test vector should be applied to an edge-sensitive pin as a fall
    followed by a rise, whereas the same 01 on a level-sensitive pin would simply be a rise.
    """

    EDGE = True
    LEVEL = False


@dataclass
class Port:
    """Encapsulate port names with role and signaling characteristics"""

    name: str
    direction: Direction
    role: Role = Role.LOGIC
    trigger: Trigger = Trigger.LEVEL

    def is_edge_triggered(self) -> bool:
        """Return whether this port is edge-triggered."""
        return bool(self.trigger)


@dataclass
class Pin(Port):
    """A port with a single physical pin."""

    is_inverted: bool = False

    def is_asserted(self, stimulus) -> bool:
        """Determine whether this pin is asserted based on the given stimulus"""
        if self.is_inverted:
            return int("0" in str(stimulus))
        return int("1" in str(stimulus))


@dataclass
class DifferentialPair(Port):
    """Encapsulate a port consisting of a differential pair of physical pins"""

    inverting_name: str = None

    def __contains__(self, item) -> bool:
        """Implements 'in' operator"""
        if isinstance(item, str):
            return item in [self.name, self.inverting_name]
        if isinstance(item, Pin):
            return item in list(self.as_pins())
        return False

    def complement(self, port_name: str) -> str | None:
        """Given the name of one port in the pair, return the other port.

        Returns None if port_name is not in the DifferentialPair."""
        if port_name == self.name:
            return self.inverting_name
        if port_name == self.inverting_name:
            return self.name
        return None

    def as_pins(self):
        """Yield each member of the diff pair as Pin objects"""
        yield Pin(self.name, self.direction, self.role, trigger=self.trigger, is_inverted=False)
        yield Pin(self.inverting_name, self.direction, self.role, trigger=self.trigger, is_inverted=True)
