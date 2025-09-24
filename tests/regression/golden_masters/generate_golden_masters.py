#!/usr/bin/env python3
"""
Golden Master Reference Generator
Generates and maintains golden master reference files for regression testing
"""

import json
import time
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


class GoldenMasterGenerator:
    """Generates and validates golden master reference files"""

    def __init__(self, base_path: Optional[Path] = None):
        """Initialize golden master generator

        Args:
            base_path: Base path for golden master files (defaults to current directory)
        """
        self.base_path = base_path or Path(__file__).parent
        self.masters_dir = self.base_path / "masters"
        self.masters_dir.mkdir(exist_ok=True)

    def generate_system_baseline(self) -> Dict[str, Any]:
        """Generate system baseline golden master

        Returns:
            Dictionary containing system baseline data
        """
        baseline = {
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "generator_version": "1.0.0",
                "baseline_type": "system_configuration"
            },
            "environment": {
                "isolation_verified": True,
                "port_assignments": {
                    "dev": 8000,
                    "test": 8181,
                    "prod": 8282
                },
                "directory_structure": [
                    "env/dev/code",
                    "env/dev/config",
                    "env/dev/data",
                    "env/dev/logs",
                    "env/test/code",
                    "env/test/config",
                    "env/test/data",
                    "env/test/logs",
                    "env/prod/code",
                    "env/prod/config",
                    "env/prod/data",
                    "env/prod/logs"
                ]
            },
            "ingestion_pipeline": {
                "pass_a_requirements": {
                    "input_format": "pdf",
                    "output_format": "chunked_text",
                    "tool": "unstructured.io",
                    "min_chunk_size": 100,
                    "max_chunk_size": 2000
                },
                "pass_b_requirements": {
                    "input_format": "chunked_text",
                    "output_format": "enriched_content",
                    "tool": "haystack",
                    "dictionary_updates": True,
                    "metadata_extraction": True
                },
                "pass_c_requirements": {
                    "input_format": "enriched_content",
                    "output_format": "graph_structure",
                    "tool": "llamaindex",
                    "relationship_mapping": True,
                    "vector_embeddings": True
                }
            },
            "rag_system": {
                "query_classification": {
                    "response_time_p95": 150,  # milliseconds
                    "accuracy_threshold": 0.85
                },
                "retrieval_policies": [
                    "vector_similarity",
                    "metadata_filtering",
                    "graph_traversal",
                    "hybrid_ranking"
                ],
                "model_routing": {
                    "simple_queries": "gpt-3.5-turbo",
                    "complex_queries": "gpt-4",
                    "code_queries": "claude-3",
                    "creative_queries": "gpt-4"
                }
            },
            "performance_thresholds": {
                "search_response_time": 2000,  # milliseconds
                "ingestion_throughput": 10,     # pages per minute
                "query_classification_time": 150,  # milliseconds
                "ui_load_time": 3000,           # milliseconds
                "api_response_time": 1000       # milliseconds
            }
        }

        # Save baseline
        self._save_golden_master("system_baseline.json", baseline)
        return baseline

    def generate_api_response_masters(self) -> Dict[str, Any]:
        """Generate golden master API response templates

        Returns:
            Dictionary containing API response templates
        """
        api_masters = {
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "master_type": "api_responses"
            },
            "search_api": {
                "basic_search_response": {
                    "results": [
                        {
                            "id": "spell_fireball_001",
                            "title": "Fireball",
                            "type": "spell",
                            "level": 3,
                            "school": "evocation",
                            "relevance_score": 0.95,
                            "source": "Player's Handbook",
                            "excerpt": "A bright streak flashes from your pointing finger..."
                        }
                    ],
                    "total_matches": 1,
                    "query_time": 0.045,
                    "facets": {
                        "spell_level": {"3": 1},
                        "spell_school": {"evocation": 1},
                        "source_book": {"Player's Handbook": 1}
                    }
                },
                "faceted_search_response": {
                    "results": [],
                    "total_matches": 0,
                    "query_time": 0.032,
                    "applied_filters": {
                        "spell_level": [1, 2],
                        "spell_school": ["conjuration"]
                    },
                    "facet_counts": {
                        "spell_level": {"1": 15, "2": 8, "3": 22},
                        "spell_school": {"conjuration": 5, "evocation": 12}
                    }
                }
            },
            "content_api": {
                "spell_detail_response": {
                    "id": "spell_magic_missile_001",
                    "name": "Magic Missile",
                    "level": 1,
                    "school": "evocation",
                    "casting_time": "1 action",
                    "range": "120 feet",
                    "components": ["V", "S"],
                    "duration": "Instantaneous",
                    "description": "You create three glowing darts of magical force...",
                    "damage": {
                        "dice": "1d4+1",
                        "type": "force",
                        "scaling": "one additional dart per slot level above 1st"
                    },
                    "classes": ["wizard", "sorcerer"],
                    "source": "Player's Handbook",
                    "page": 257
                },
                "spell_list_response": {
                    "spells": [],
                    "total_count": 0,
                    "page": 1,
                    "page_size": 20,
                    "filters_applied": [],
                    "sort_order": "alphabetical"
                }
            },
            "admin_api": {
                "ingestion_status_response": {
                    "job_id": "ing_20240315_143022",
                    "status": "completed",
                    "progress": 100,
                    "phases": {
                        "pass_a": {"status": "completed", "duration": 45.2, "chunks_created": 1247},
                        "pass_b": {"status": "completed", "duration": 32.8, "items_enriched": 1247},
                        "pass_c": {"status": "completed", "duration": 67.1, "relationships_mapped": 3891}
                    },
                    "total_duration": 145.1,
                    "created_at": "2024-03-15T14:30:22Z",
                    "completed_at": "2024-03-15T14:32:47Z"
                },
                "system_health_response": {
                    "status": "healthy",
                    "services": {
                        "database": {"status": "healthy", "response_time": 12},
                        "vector_store": {"status": "healthy", "response_time": 8},
                        "ai_models": {"status": "healthy", "response_time": 156}
                    },
                    "performance_metrics": {
                        "avg_query_time": 89,
                        "active_sessions": 15,
                        "cache_hit_rate": 0.78
                    },
                    "last_check": "2024-03-15T14:35:00Z"
                }
            }
        }

        self._save_golden_master("api_responses.json", api_masters)
        return api_masters

    def generate_ui_component_masters(self) -> Dict[str, Any]:
        """Generate golden master UI component structures

        Returns:
            Dictionary containing UI component templates
        """
        ui_masters = {
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "master_type": "ui_components"
            },
            "search_interface": {
                "search_form_structure": {
                    "query_input": {
                        "type": "text",
                        "placeholder": "Search spells, items, creatures...",
                        "autocomplete": True,
                        "validation": "required"
                    },
                    "filter_panels": [
                        {
                            "name": "Content Type",
                            "field": "content_type",
                            "options": ["spell", "item", "creature", "rule"]
                        },
                        {
                            "name": "Source",
                            "field": "source_book",
                            "options": ["Player's Handbook", "Dungeon Master's Guide", "Monster Manual"]
                        }
                    ],
                    "sort_options": [
                        {"value": "relevance", "label": "Relevance"},
                        {"value": "alphabetical", "label": "A-Z"},
                        {"value": "level_asc", "label": "Level (Low to High)"}
                    ]
                },
                "search_results_structure": {
                    "result_card": {
                        "title": "string",
                        "type_badge": "string",
                        "level_indicator": "number|null",
                        "excerpt": "string",
                        "source_citation": "string",
                        "relevance_score": "number",
                        "action_buttons": ["view", "favorite", "share"]
                    },
                    "pagination": {
                        "current_page": "number",
                        "total_pages": "number",
                        "page_size": "number",
                        "total_results": "number"
                    }
                }
            },
            "admin_interface": {
                "ingestion_dashboard": {
                    "job_queue": {
                        "pending_jobs": "array",
                        "active_jobs": "array",
                        "completed_jobs": "array",
                        "failed_jobs": "array"
                    },
                    "progress_indicators": {
                        "overall_progress": "number",
                        "phase_progress": "object",
                        "eta_remaining": "string"
                    },
                    "action_controls": [
                        "start_ingestion",
                        "pause_ingestion",
                        "cancel_ingestion",
                        "retry_failed"
                    ]
                },
                "system_monitoring": {
                    "health_indicators": {
                        "database_status": "string",
                        "api_status": "string",
                        "ingestion_status": "string"
                    },
                    "performance_charts": [
                        "query_response_times",
                        "ingestion_throughput",
                        "error_rates",
                        "cache_performance"
                    ]
                }
            },
            "user_interface": {
                "retro_terminal_theme": {
                    "color_scheme": {
                        "background": "#000000",
                        "foreground": "#00ff00",
                        "accent": "#ffff00",
                        "error": "#ff0000"
                    },
                    "typography": {
                        "font_family": "Courier New, monospace",
                        "font_size": "14px",
                        "line_height": "1.4"
                    },
                    "animations": {
                        "typing_effect": True,
                        "scan_lines": True,
                        "cursor_blink": True
                    }
                },
                "lcars_theme": {
                    "color_scheme": {
                        "background": "#000000",
                        "primary": "#ff9900",
                        "secondary": "#9999ff",
                        "accent": "#ffcc99"
                    },
                    "interface_elements": {
                        "rounded_corners": "20px",
                        "button_style": "lcars_button",
                        "panel_borders": "none"
                    }
                }
            }
        }

        self._save_golden_master("ui_components.json", ui_masters)
        return ui_masters

    def generate_test_data_masters(self) -> Dict[str, Any]:
        """Generate golden master test data sets

        Returns:
            Dictionary containing test data templates
        """
        test_masters = {
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "master_type": "test_data"
            },
            "sample_spells": [
                {
                    "id": "test_spell_001",
                    "name": "Test Fireball",
                    "level": 3,
                    "school": "evocation",
                    "casting_time": "1 action",
                    "range": "150 feet",
                    "components": ["V", "S", "M"],
                    "material_components": "a tiny ball of bat guano and sulfur",
                    "duration": "instantaneous",
                    "description": "A bright streak flashes from your pointing finger to a point you choose within range and then blossoms with a low roar into an explosion of flame.",
                    "damage": {
                        "dice": "8d6",
                        "type": "fire",
                        "scaling": "1d6 per slot level above 3rd"
                    },
                    "saving_throw": {
                        "ability": "dexterity",
                        "dc": "spell_save_dc",
                        "success": "half_damage"
                    },
                    "area_of_effect": {
                        "shape": "sphere",
                        "size": "20-foot radius"
                    },
                    "classes": ["wizard", "sorcerer"],
                    "source": "Test Data",
                    "tags": ["damage", "area_effect", "fire"]
                }
            ],
            "sample_queries": [
                {
                    "query": "fireball spell",
                    "expected_results": 1,
                    "expected_top_result": "test_spell_001",
                    "query_type": "basic_search"
                },
                {
                    "query": "fire damage spells level 3",
                    "expected_results": 1,
                    "facets": {
                        "spell_level": [3],
                        "damage_type": ["fire"]
                    },
                    "query_type": "faceted_search"
                },
                {
                    "query": "area of effect evocation",
                    "expected_results": 1,
                    "filters": {
                        "school": ["evocation"],
                        "has_area_effect": True
                    },
                    "query_type": "filtered_search"
                }
            ],
            "performance_benchmarks": {
                "search_queries": [
                    {
                        "query": "magic missile",
                        "max_response_time": 100,  # milliseconds
                        "min_results": 1
                    },
                    {
                        "query": "healing spells level 1",
                        "max_response_time": 150,
                        "min_results": 0
                    }
                ],
                "ingestion_benchmarks": {
                    "small_pdf": {
                        "page_count": 10,
                        "max_processing_time": 300,  # seconds
                        "min_chunks_created": 50
                    },
                    "medium_pdf": {
                        "page_count": 100,
                        "max_processing_time": 1800,
                        "min_chunks_created": 500
                    }
                }
            }
        }

        self._save_golden_master("test_data.json", test_masters)
        return test_masters

    def generate_configuration_masters(self) -> Dict[str, Any]:
        """Generate golden master configuration templates

        Returns:
            Dictionary containing configuration templates
        """
        config_masters = {
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "master_type": "configurations"
            },
            "environment_configs": {
                "dev_config": {
                    "debug": True,
                    "port": 8000,
                    "log_level": "DEBUG",
                    "cache_ttl": 5,  # seconds
                    "database_pool_size": 5,
                    "ai_model_timeout": 30,
                    "ingestion_parallel_workers": 2
                },
                "test_config": {
                    "debug": False,
                    "port": 8181,
                    "log_level": "INFO",
                    "cache_ttl": 60,
                    "database_pool_size": 3,
                    "ai_model_timeout": 15,
                    "ingestion_parallel_workers": 1
                },
                "prod_config": {
                    "debug": False,
                    "port": 8282,
                    "log_level": "WARNING",
                    "cache_ttl": 3600,
                    "database_pool_size": 20,
                    "ai_model_timeout": 60,
                    "ingestion_parallel_workers": 4
                }
            },
            "database_configs": {
                "astradb_config": {
                    "keyspace": "ttrpg_center",
                    "region": "us-east-2",
                    "vector_dimension": 1536,
                    "similarity_metric": "cosine",
                    "connection_timeout": 30,
                    "read_timeout": 60
                }
            },
            "ai_model_configs": {
                "openai_config": {
                    "default_model": "gpt-3.5-turbo",
                    "max_tokens": 2048,
                    "temperature": 0.7,
                    "timeout": 30
                },
                "classification_config": {
                    "model": "gpt-3.5-turbo",
                    "max_tokens": 100,
                    "temperature": 0.1,
                    "response_format": "json"
                }
            }
        }

        self._save_golden_master("configurations.json", config_masters)
        return config_masters

    def _save_golden_master(self, filename: str, data: Dict[str, Any]) -> Path:
        """Save golden master data to file

        Args:
            filename: Name of the file to save
            data: Data to save

        Returns:
            Path to saved file
        """
        file_path = self.masters_dir / filename

        # Add checksum for integrity validation
        data_str = json.dumps(data, sort_keys=True, indent=2)
        data["metadata"]["checksum"] = hashlib.sha256(data_str.encode()).hexdigest()

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return file_path

    def validate_golden_master(self, filename: str) -> Dict[str, Any]:
        """Validate a golden master file

        Args:
            filename: Name of the file to validate

        Returns:
            Validation result dictionary
        """
        file_path = self.masters_dir / filename

        if not file_path.exists():
            return {"valid": False, "error": "File not found"}

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Validate structure
            if "metadata" not in data:
                return {"valid": False, "error": "Missing metadata"}

            # Validate checksum if present
            if "checksum" in data["metadata"]:
                stored_checksum = data["metadata"]["checksum"]

                # Create copy without checksum for validation
                validation_data = data.copy()
                del validation_data["metadata"]["checksum"]

                data_str = json.dumps(validation_data, sort_keys=True, indent=2)
                calculated_checksum = hashlib.sha256(data_str.encode()).hexdigest()

                if stored_checksum != calculated_checksum:
                    return {"valid": False, "error": "Checksum mismatch"}

            return {"valid": True, "data": data}

        except Exception as e:
            return {"valid": False, "error": str(e)}

    def generate_all_masters(self) -> Dict[str, Path]:
        """Generate all golden master files

        Returns:
            Dictionary mapping master type to file path
        """
        generated_files = {}

        print("Generating system baseline golden master...")
        self.generate_system_baseline()
        generated_files["system_baseline"] = self.masters_dir / "system_baseline.json"

        print("Generating API response golden masters...")
        self.generate_api_response_masters()
        generated_files["api_responses"] = self.masters_dir / "api_responses.json"

        print("Generating UI component golden masters...")
        self.generate_ui_component_masters()
        generated_files["ui_components"] = self.masters_dir / "ui_components.json"

        print("Generating test data golden masters...")
        self.generate_test_data_masters()
        generated_files["test_data"] = self.masters_dir / "test_data.json"

        print("Generating configuration golden masters...")
        self.generate_configuration_masters()
        generated_files["configurations"] = self.masters_dir / "configurations.json"

        return generated_files


def main():
    """Main entry point for golden master generation"""
    generator = GoldenMasterGenerator()

    print("TTRPG Center - Golden Master Reference Generator")
    print("=" * 50)

    generated_files = generator.generate_all_masters()

    print("\nGenerated golden master files:")
    for master_type, file_path in generated_files.items():
        print(f"  {master_type}: {file_path}")

        # Validate the generated file
        validation = generator.validate_golden_master(file_path.name)
        if validation["valid"]:
            print(f"    ✓ Validation passed")
        else:
            print(f"    ✗ Validation failed: {validation['error']}")

    print(f"\nGolden masters saved to: {generator.masters_dir}")
    print("Use these files as reference for regression testing.")


if __name__ == "__main__":
    main()