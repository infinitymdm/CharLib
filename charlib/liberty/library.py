import itertools
from typing import Final

import numpy as np

from charlib import liberty


class Library(liberty.Group):
    """Convenience class for liberty library groups with pre-populated defaults"""

    # These must be displayed first if present, and in the order below
    ORDERED_ATTRIBUTES: Final[list[str]] = [
        "technology",
        "delay_model",
        "bus_naming_style",
        "date",
        "comment",
        "time_unit",
        "voltage_unit",
        "leakage_power_unit",
        "current_unit",
        "pulling_resistance_unit",
        "capacitive_load_unit",
        "revision",
        "in_place_swap_mode",
    ]
    ORDERED_GROUPS: Final[list[str]] = [
        "operating_conditions",
        "lu_table_template",
        "cell",
    ]

    def __init__(self, name, **attrs):
        """Construct a library group"""
        super().__init__("library", name)
        self.file_name = attrs.pop("filename", f"{name}.lib")
        self.add_attribute("technology", "cmos")
        self.add_attribute("delay_model", "table_lookup")
        self.add_attribute("bus_naming_style", "%s-%d")

        # Add nominal operating conditions
        self.add_attribute("nom_process", 1.0, 2)
        self.add_attribute("nom_voltage", 3.3, 2)  # FIXME: This isn't a sane default. Needs user input
        self.add_attribute("nom_temperature", 25.0, 2)

        # Override defaults with whatever attrs get passed as kwargs
        [self.add_attribute(attr_name, value, 2) for attr_name, value in attrs.items()]

        # Copy nom_* attrs into operating_conditions group
        # TODO: Make op_conditions identifier configurable
        op_conditions = liberty.Group("operating_conditions", "typical")
        op_conditions.add_attribute(
            "process", self.attributes["nom_process"].value, self.attributes["nom_process"].precision
        )
        op_conditions.add_attribute(
            "voltage", self.attributes["nom_voltage"].value, self.attributes["nom_voltage"].precision
        )
        op_conditions.add_attribute(
            "temperature", self.attributes["nom_temperature"].value, self.attributes["nom_temperature"].precision
        )
        self.add_group(op_conditions)

    @property
    def cells(self) -> list:
        """Return cell groups."""
        return [group for group in self.groups if group.name == "cell"]

    def to_liberty(self, **kwargs):
        """Convert this library to a Liberty-format string.

        :param precision: Digits of floating-point precision to display. Default 1
        """
        # TODO: Rework precision kwarg into a dict of group.name: precision values
        # Library display order is specialized
        lib_str = [f"{self.name} ({self.identifier}){{"]
        for attr in self.ORDERED_ATTRIBUTES:
            if attr in self.attributes:
                lib_str += [self.attributes[attr].to_liberty(1, **kwargs)]
        for key, attr in self.attributes.items():
            if key not in self.ORDERED_ATTRIBUTES:
                lib_str += [attr.to_liberty(1, **kwargs)]
        for group_name in self.ORDERED_GROUPS:
            for group in self.subgroups_with_name(group_name):
                lib_str += group.to_liberty(1, **kwargs).split("\n")
        for group in self.groups.values():
            if group.name not in self.ORDERED_GROUPS:
                lib_str += group.to_liberty(1, **kwargs).split("\n")
        lib_str += [f"}} /* end {self.name} */"]
        return "\n".join(lib_str)


class LookupTableTemplate(liberty.Group):
    """Convenience class for lu_table_template groups, which have slightly unusual formatting

    While lut templates are normal groups, they have quite a bit of odd formatting. Indices, for
    example, are complex attributes with a single long string value of comma-separated floats
    corresponding to one of the variables. Moreover, we don't care about the values in the indices
    as they are overridden by tables using these templates.
    """

    def __init__(self, lut_name, **variables):
        """Initialize a lu_table_template group

        :param lut_name: The identifier for the lu_table_template group.
        :param **variables: keyword arguments consisting of variable names and integer sizes.
        """
        super().__init__("lu_table_template", lut_name)
        self.variables = variables

    @property
    def size(self):
        """Return size as a shape-like tuple"""
        return tuple(self.variables.values())

    def to_liberty(self, indent_level=0, **kwargs):
        # LUT template display order is specialized
        indent = liberty.INDENT_STR * indent_level
        lut_str = [f"{indent}{self.name} ({self.identifier}) {{"]

        # Construct & display variables
        index = 0
        for variable in self.variables.keys():
            index += 1
            lut_str += [liberty.Attribute(f"variable_{index}", variable).to_liberty(indent_level + 1, **kwargs)]

        # Construct & display indices
        index = 0
        for length in self.variables.values():
            index += 1
            values = ['"' + ", ".join([str(1.0 + i) for i in range(length)]) + '"']
            lut_str += [liberty.Attribute(f"index_{index}", values).to_liberty(indent_level + 1, **kwargs)]

        # LUT templates may also have sub-groups, but no attributes
        for group in self.groups.values():
            lut_str += group.to_liberty(indent_level + 1, **kwargs).split("\n")
        lut_str += [f"{indent}}} /* end {self.name} */"]
        return "\n".join(lut_str)


class LookupTable(liberty.Group):
    """Convenience class for lookup tables.

    LookupTables have odd formatting like LookupTableTemplates, but also need improved tools for
    quickly accessing and manipulating data. Variable values and table contents are stored as numpy
    arrays and matrices respectively.
    """

    def __init__(self, lut_name, lut_template, **variable_values):
        """Initialize a lookup table from a template

        :param lut_name: The name of the lookup table.
        :param lut_template: A LookupTableTemplate group or lu_table_template name to create.
        :param **variable_values: keyword arguments consisting of variable names and values.
        """
        if not isinstance(lut_template, LookupTableTemplate):
            lut_template = LookupTableTemplate(lut_template, **{k: len(v) for k, v in variable_values.items()})
        else:
            # Validate that variable names, lengths, and positions match up with template
            for (var, values), (template_var, length) in zip(variable_values.items(), lut_template.variables.items()):
                if not var == template_var:
                    index = list(lut_template.keys()).index(template_var)
                    raise ValueError(f'Template requires variable_{index} = "{template_var}", got "{var}"')
                if not len(values) == length:
                    raise ValueError(f'Template requires variable "{var}" to have {length} values, got {len(values)}')
        super().__init__(lut_name, lut_template.identifier)
        self.template = lut_template

        # Store index values as numpy arrays
        self.index_values = [np.array(v) for v in variable_values.values()]

        # Store table values as a matrix
        self.values = np.zeros(self.size)

    @property
    def size(self):
        """Return template size"""
        return self.template.size

    def _get_indices(self, *index_values):
        """Determine the indices matching the ordered list of index values passed"""
        indices = []
        for key, i in zip(index_values, range(len(self.size))):
            try:
                indices += [int(np.argwhere(self.index_values[i] == key)[0][0])]
            except IndexError:
                raise KeyError(f"index_{i + 1} contains no such value: {key}")
        return indices

    def __getitem__(self, keys):
        # Lookup and return value by indices
        return self.values[*self._get_indices(*keys)]

    def __setitem__(self, keys, value):
        # Lookup and set value by indices
        self.values[*self._get_indices(*keys)] = value

    def merge(self, other):
        """Merge two LUTs & update templates"""
        super().merge(other)  # This will usually do nothing aside from validating hashes match

        # Merge LUT templates as long as variable names are the same
        if not self.template.variables.keys() == other.template.variables.keys():
            raise ValueError("LUT template variable names must match in order to merge!")

        # Merge LUT variable values
        merged_template_variables = {}
        merged_index_values = []
        for i, variable in zip(range(len(self.index_values)), self.template.variables.keys()):
            merged = set(self.index_values[i]).union(set(other.index_values[i]))
            merged_index_values.append(np.array(sorted([*merged])))
            merged_template_variables[variable] = len(merged)

        # Merge LUT table values, always preferring nonzeros
        values = [(index_values, self[*index_values]) for index_values in itertools.product(*self.index_values)]
        values += [(index_values, other[*index_values]) for index_values in itertools.product(*other.index_values)]
        merged_values = np.zeros(tuple(merged_template_variables.values()))
        self.template.variables = merged_template_variables
        self.index_values = merged_index_values
        for index_values, value in values:
            if not merged_values[*self._get_indices(*index_values)]:
                merged_values[*self._get_indices(*index_values)] = value
        self.values = merged_values

    def to_liberty(self, indent_level=0, precision=1, **kwargs):
        # LUT display requires reformatting indices and variables
        indent = liberty.INDENT_STR * indent_level
        inner_indent = liberty.INDENT_STR * (indent_level + 1)
        value_indent = liberty.INDENT_STR * (indent_level + 2)

        lut_str = [f"{indent}{self.name} ({self.identifier}) {{"]

        # Display index values
        for i in range(len(self.index_values)):
            index_values = [f"{v:.{precision}f}" for v in self.index_values[i]]
            lut_str += [f'{inner_indent}index_{i + 1} ("{", ".join(index_values)}") ;']

        # Display LUT values
        lut_str += [f"{inner_indent}values ( \\"]
        sets = 1 if len(self.index_values) < 3 else len(self.index_values[2])
        for s in range(sets):
            for i in range(len(self.index_values[0])):
                values = [f"{v:.{precision}f}" for v in np.atleast_3d(self.values)[i, :, s]]
                lut_str += [f'{value_indent}"{", ".join(values)}" \\']
        lut_str += [f"{inner_indent}) ;"]
        lut_str += [f"{indent}}} /* end {self.name} */"]
        return "\n".join(lut_str)
