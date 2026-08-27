import re
from collections.abc import Iterator
from pathlib import Path

import yaml
from schema import SchemaError

from charlib.config.syntax import ConfigFile


def find_yaml_files(path: str | Path) -> list:
    """Return a list of Paths containing all YAML files in the directory specified by `path`."""
    path = Path(path)
    if path.is_file():
        return [path]
    elif path.is_dir():
        return list(path.rglob("*.yaml")) + list(path.rglob("*.yml"))
    else:
        return []


def resolve_subkey(value: str, base_dir: str | Path):
    """If a config value ends in .yml or .yaml, resolve it to the YAML contents."""
    if isinstance(value, str):
        if not value.lower().endswith((".yml", ".yaml")):
            return value
        possible_yamls = find_yaml_files(Path(base_dir) / value)
        if len(possible_yamls) != 1:
            raise ValueError(f"Unable to resolve {value} to a unique existing file")
        with open(possible_yamls[0]) as file:
            return yaml.safe_load(file)
    return value


def find_config(config_path: str | Path, quiet: bool = False) -> dict:
    """Find an appropriately-formatted YAML file in `config_path`"""

    if not quiet:
        print(f"Searching for YAML files at {config_path!s}")
    config = None
    for file in find_yaml_files(config_path):
        # Load the file
        try:
            with open(file) as f:
                config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            if not quiet:
                print(e)
                print(f'Skipping "{file!s}": file contains invalid YAML')
            continue
        # Ensure the file contains a config dictionary
        if not isinstance(config, dict):
            if not quiet:
                print(f'Skipping "{file!s}": file does not contain a config dict')
            continue
        # Substitute in config keys which point to other YAML files or directories
        config = {k: resolve_subkey(v, file.parent) for k, v in config.items()}
        # Validate the schema
        try:
            config = ConfigFile.validate(config)
            break  # Exit on success
        except SchemaError as e:
            if not quiet:
                print(e)
                print(f'Skipping "{file!s}": file does not contain a valid CharLib config')
            config = None
    if not isinstance(config, dict):
        raise FileNotFoundError(f"No valid configuration found in {config_path}")
    return config


def filter_cells(cells: dict, filters: list) -> dict:
    """Filter the dict of cells by name against a list of regex filter patterns.

    :param cells: A dict indexed by cell name
    :param filters: A list of regex strings to filter cell names against
    :returns: A dict indexed by cell name where all cell names match one or more filter regex strings
    """
    filtered_cells = {}
    filters = [re.compile(f) for f in filters]
    for name, cell in cells.items():  # Check each cell name against each filter pattern until we get a match
        for pattern in filters:
            if pattern.search(name):
                filtered_cells[name] = cell
                break  # We've already matched this cell, quit searching
    return filtered_cells


def read_cell_configs(cells, quiet=False) -> Iterator[tuple]:
    """Yield cell names and property dicts from a dict of cells.

    This function also handles the case where cell properties are stored in another file. In this
    case it reads the file and makes sure the properties are in dict format.

    :param cells: A dict indexed by cell name
    :param quiet: Whether to suppress print statements
    """
    for name, properties in cells.items():
        # If properties is a (name, filepath) pair, fetch cell config from YAML at filepath
        if isinstance(properties, str):
            # Search the directory for valid YAML
            for file in find_yaml_files(properties):
                try:
                    with open(file, "r") as f:
                        cell_config = yaml.safe_load(f)
                    break  # Quit searching after successfully reading a match
                except yaml.YAMLError as e:
                    if not quiet:
                        print(e)
                        print(f'Skipping "{file!s}": file contains invalid YAML')
                    continue
        elif isinstance(properties, dict):
            cell_config = properties
        else:
            raise TypeError(f'Config for cell "{name}" must be of type str or dict, got {type(properties).__name__}')
        yield (name, cell_config)
