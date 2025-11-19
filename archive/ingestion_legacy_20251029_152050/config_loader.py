#!/usr/bin/env python3
"""
config_loader.py - Configuration Management for Ingestion Pipeline
===================================================================

Loads and validates configuration from ingestion.cfg file.
Provides type-safe access to configuration parameters for each pass.

Usage:
    from config_loader import load_config, get_pass_config

    config = load_config()  # Loads from ./ingestion.cfg
    gate0_cfg = get_pass_config(config, 'Gate_0')

    # Access with defaults
    output_dir = gate0_cfg.get('output_dir', '/Transfer_Station/Gate_0_Out')

Version: 1.0.0
Author: n8n TTRPG Center
"""

import configparser
import sys
from pathlib import Path
from typing import Dict, Any, Optional, Union

try:
    from .path_utils import resolve_transfer_path  # type: ignore
except ImportError:  # pragma: no cover - script entrypoint fallback
    from path_utils import resolve_transfer_path


__version__ = "1.0.0"

DEFAULT_CONFIG_PATH = Path(__file__).parent / "ingestion.cfg"


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""
    pass


def load_config(config_path: Optional[Path] = None) -> configparser.ConfigParser:
    """
    Load configuration from INI file.

    Args:
        config_path: Path to configuration file (default: ./ingestion.cfg)

    Returns:
        ConfigParser instance with loaded configuration

    Raises:
        ConfigurationError: If config file not found or invalid
    """
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH

    if not config_path.exists():
        raise ConfigurationError(
            f"Configuration file not found: {config_path}\n"
            f"Expected location: {DEFAULT_CONFIG_PATH}"
        )

    config = configparser.ConfigParser()

    try:
        config.read(config_path)
    except Exception as e:
        raise ConfigurationError(f"Failed to parse configuration file: {e}")

    if not config.sections():
        raise ConfigurationError(
            f"Configuration file is empty or invalid: {config_path}"
        )

    return config


def get_pass_config(
    config: configparser.ConfigParser,
    pass_name: str,
    required: bool = False
) -> Dict[str, str]:
    """
    Get configuration section for a specific pass.

    Args:
        config: ConfigParser instance
        pass_name: Name of pass (e.g., 'Gate_0', 'Pass_A', 'Pass_D')
        required: If True, raise error if section not found

    Returns:
        Dictionary of configuration parameters

    Raises:
        ConfigurationError: If section required but not found
    """
    if not config.has_section(pass_name):
        if required:
            raise ConfigurationError(
                f"Required configuration section not found: [{pass_name}]"
            )
        return {}

    return dict(config[pass_name])


def get_config_value(
    config: Dict[str, str],
    key: str,
    default: Any = None,
    value_type: type = str
) -> Any:
    """
    Get configuration value with type conversion and default.

    Args:
        config: Configuration dictionary
        key: Configuration key
        default: Default value if key not found
        value_type: Type to convert value to (str, int, float, bool, Path)

    Returns:
        Configured value or default, converted to specified type

    Raises:
        ConfigurationError: If type conversion fails
    """
    value = config.get(key)

    if value is None:
        return default

    try:
        # Handle boolean conversion
        if value_type == bool:
            return value.lower() in ('true', 'yes', '1', 'on')

        # Handle Path conversion
        if value_type == Path:
            return Path(value)

        # Standard type conversion
        return value_type(value)

    except (ValueError, TypeError) as e:
        raise ConfigurationError(
            f"Failed to convert config value '{key}={value}' to {value_type.__name__}: {e}"
        )


def validate_required_keys(config: Dict[str, str], required_keys: list, pass_name: str):
    """
    Validate that required configuration keys are present.

    Args:
        config: Configuration dictionary
        required_keys: List of required key names
        pass_name: Name of pass (for error message)

    Raises:
        ConfigurationError: If any required keys are missing
    """
    missing = [key for key in required_keys if key not in config]

    if missing:
        raise ConfigurationError(
            f"Missing required configuration for [{pass_name}]: {', '.join(missing)}"
        )


def get_gate0_config(config: configparser.ConfigParser) -> Dict[str, Any]:
    """Get typed Gate 0 configuration."""
    cfg = get_pass_config(config, 'Gate_0')

    return {
        'output_dir': get_config_value(cfg, 'output_dir', str(resolve_transfer_path('Gate_0_Out')), Path),
    }


def get_pass_a_config(config: configparser.ConfigParser) -> Dict[str, Any]:
    """Get typed Pass A configuration."""
    cfg = get_pass_config(config, 'Pass_A')

    return {
        'output_dir': get_config_value(cfg, 'output_dir', str(resolve_transfer_path('Pass_A_Out')), Path),
        'unstructured_strategy': get_config_value(cfg, 'unstructured_strategy', 'hi_res'),
        'ocr_language': get_config_value(cfg, 'ocr_language', 'eng'),
        'toc_start_page': get_config_value(cfg, 'toc_start_page', 1, int),
        'toc_end_page': get_config_value(cfg, 'toc_end_page', 8, int),
        'mongo_host': get_config_value(cfg, 'mongo_host', 'n8n_TTRPG_mongodb'),
        'mongo_port': get_config_value(cfg, 'mongo_port', 27017, int),
        'mongo_db': get_config_value(cfg, 'mongo_db', 'ttrpg_ingestion'),
    }


def get_pass_b_config(config: configparser.ConfigParser) -> Dict[str, Any]:
    """Get typed Pass B configuration."""
    cfg = get_pass_config(config, 'Pass_B')

    return {
        'output_dir': get_config_value(cfg, 'output_dir', str(resolve_transfer_path('Pass_B_Out')), Path),
        'min_pages': get_config_value(cfg, 'min_pages', 10, int),
        'max_pages': get_config_value(cfg, 'max_pages', 20, int),
    }


def get_pass_c_config(config: configparser.ConfigParser) -> Dict[str, Any]:
    """Get typed Pass C configuration."""
    cfg = get_pass_config(config, 'Pass_C')

    return {
        'input_dir': get_config_value(cfg, 'input_dir', str(resolve_transfer_path('Pass_C_Out')), Path),
        'output_dir': get_config_value(cfg, 'output_dir', str(resolve_transfer_path('Pass_C_Out')), Path),
        'game_system': get_config_value(cfg, 'game_system', 'auto'),
        'publisher': get_config_value(cfg, 'publisher', 'auto'),
        'mongo_host': get_config_value(cfg, 'mongo_host', 'n8n_TTRPG_mongodb'),
        'mongo_port': get_config_value(cfg, 'mongo_port', 27017, int),
        'mongo_db': get_config_value(cfg, 'mongo_db', 'ttrpg_ingestion'),
    }


def get_pass_d_config(config: configparser.ConfigParser) -> Dict[str, Any]:
    """Get typed Pass D configuration."""
    cfg = get_pass_config(config, 'Pass_D')

    return {
        'output_dir': get_config_value(cfg, 'output_dir', str(resolve_transfer_path('Pass_D_Out')), Path),
        'cassandra_host': get_config_value(cfg, 'cassandra_host', 'n8n_TTRPG_cassandra'),
        'cassandra_port': get_config_value(cfg, 'cassandra_port', 9042, int),
        'cassandra_keyspace': get_config_value(cfg, 'cassandra_keyspace', 'ttrpg_vectors'),
        'embedding_model': get_config_value(cfg, 'embedding_model', 'text-embedding-3-small'),
        'min_chunk_chars': get_config_value(cfg, 'min_chunk_chars', 500, int),
        'max_chunk_chars': get_config_value(cfg, 'max_chunk_chars', 600, int),
        'chunk_overlap': get_config_value(cfg, 'chunk_overlap', 50, int),
        'batch_size': get_config_value(cfg, 'batch_size', 100, int),
    }


def get_pass_e_config(config: configparser.ConfigParser) -> Dict[str, Any]:
    """Get typed Pass E configuration."""
    cfg = get_pass_config(config, 'Pass_E')

    return {
        'output_dir': get_config_value(cfg, 'output_dir', str(resolve_transfer_path('Pass_E_Out')), Path),
        'cassandra_host': get_config_value(cfg, 'cassandra_host', 'n8n_TTRPG_cassandra'),
        'cassandra_port': get_config_value(cfg, 'cassandra_port', 9042, int),
        'cassandra_keyspace': get_config_value(cfg, 'cassandra_keyspace', 'ttrpg_vectors'),
        'neo4j_host': get_config_value(cfg, 'neo4j_host', 'n8n_TTRPG_neo4j'),
        'neo4j_port': get_config_value(cfg, 'neo4j_port', 7687, int),
        'neo4j_database': get_config_value(cfg, 'neo4j_database', 'neo4j'),
        'enable_similarity': get_config_value(cfg, 'enable_similarity', False, bool),
        'similarity_threshold': get_config_value(cfg, 'similarity_threshold', 0.82, float),
        'similarity_top_k': get_config_value(cfg, 'similarity_top_k', 5, int),
        'llamaindex_url': get_config_value(cfg, 'llamaindex_url', 'http://n8n_TTRPG_llamaindex:8000'),
    }


def print_config_summary(config: configparser.ConfigParser):
    """Print configuration summary for debugging."""
    print("Configuration Summary")
    print("=" * 60)

    for section in config.sections():
        print(f"\n[{section}]")
        for key, value in config[section].items():
            print(f"  {key} = {value}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    """Test configuration loading."""
    try:
        config = load_config()
        print_config_summary(config)

        print("\nTyped configurations:")
        print("\nGate 0:", get_gate0_config(config))
        print("\nPass A:", get_pass_a_config(config))
        print("\nPass B:", get_pass_b_config(config))
        print("\nPass C:", get_pass_c_config(config))
        print("\nPass D:", get_pass_d_config(config))
        print("\nPass E:", get_pass_e_config(config))
    except ConfigurationError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
