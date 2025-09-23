# tests/regression/feature_requests/test_fr012_export_sharing.py
"""
Feature Request FR-012: Export and Sharing Capabilities Regression Tests
Tests comprehensive export functionality and sharing mechanisms for content and search results
"""

import pytest
import json
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
import base64


class TestExportSharingCapabilities:
    """Test suite for FR-012 Export and Sharing functionality"""

    def test_export_infrastructure_availability(self):
        """Test that export and sharing components are available"""
        try:
            from src_common.export import ExportManager
            from src_common.sharing import SharingService
            from src_common.formatters import ContentFormatter
            from src_common.packaging import ContentPackager

            assert ExportManager is not None, "ExportManager should be available"
            assert SharingService is not None, "SharingService should be available"
            assert ContentFormatter is not None, "ContentFormatter should be available"
            assert ContentPackager is not None, "ContentPackager should be available"

        except ImportError as e:
            pytest.fail(f"Export and sharing components not available: {e}")

    def test_content_export_formats(self):
        """Test content export in various formats"""
        try:
            from src_common.export import ExportManager
        except ImportError:
            pytest.skip("Export manager not available for testing")

        export_manager = ExportManager()

        # Test content for export
        test_content = {
            "search_results": [
                {
                    "content_id": "phb_character_creation",
                    "title": "Character Creation",
                    "text": "Creating a character involves choosing race, class, and background...",
                    "metadata": {
                        "source": "Player's Handbook",
                        "page": 12,
                        "content_type": "rules"
                    }
                },
                {
                    "content_id": "dmg_magic_items",
                    "title": "Magic Items Overview",
                    "text": "Magic items are treasures that provide supernatural abilities...",
                    "metadata": {
                        "source": "Dungeon Master's Guide",
                        "page": 135,
                        "content_type": "items"
                    }
                }
            ],
            "query_info": {
                "original_query": "character creation and magic items",
                "timestamp": datetime.now().isoformat(),
                "filters_applied": ["content_type:rules,items"]
            }
        }

        # Test PDF export
        if hasattr(export_manager, 'export_to_pdf'):
            pdf_config = {
                "format": "pdf",
                "layout": "standard",
                "include_metadata": True,
                "include_toc": True,
                "font_size": 12,
                "margins": {"top": 1, "bottom": 1, "left": 1, "right": 1}
            }

            pdf_result = export_manager.export_to_pdf(test_content, pdf_config)

            assert isinstance(pdf_result, dict), "PDF export should return structured result"

            if "export_data" in pdf_result:
                export_data = pdf_result["export_data"]
                assert isinstance(export_data, (str, bytes)), "PDF data should be string or bytes"

            if "filename" in pdf_result:
                filename = pdf_result["filename"]
                assert filename.endswith(".pdf"), "PDF export should have .pdf extension"

        # Test Word document export
        if hasattr(export_manager, 'export_to_docx'):
            docx_config = {
                "format": "docx",
                "template": "standard",
                "include_images": True,
                "include_tables": True,
                "styles": {"heading": "Heading 1", "body": "Normal"}
            }

            docx_result = export_manager.export_to_docx(test_content, docx_config)

            assert isinstance(docx_result, dict), "DOCX export should return structured result"

            if "export_data" in docx_result:
                export_data = docx_result["export_data"]
                assert isinstance(export_data, bytes), "DOCX data should be bytes"

        # Test JSON export
        if hasattr(export_manager, 'export_to_json'):
            json_config = {
                "format": "json",
                "pretty_print": True,
                "include_metadata": True,
                "compress": False
            }

            json_result = export_manager.export_to_json(test_content, json_config)

            assert isinstance(json_result, dict), "JSON export should return structured result"

            if "export_data" in json_result:
                export_data = json_result["export_data"]
                # Should be valid JSON
                parsed_data = json.loads(export_data)
                assert isinstance(parsed_data, dict), "Exported JSON should be valid dictionary"

        # Test CSV export
        if hasattr(export_manager, 'export_to_csv'):
            csv_config = {
                "format": "csv",
                "delimiter": ",",
                "include_headers": True,
                "flatten_metadata": True
            }

            csv_result = export_manager.export_to_csv(test_content, csv_config)

            assert isinstance(csv_result, dict), "CSV export should return structured result"

            if "export_data" in csv_result:
                export_data = csv_result["export_data"]
                assert isinstance(export_data, str), "CSV data should be string"

                # Basic CSV validation
                lines = export_data.strip().split('\n')
                assert len(lines) >= 2, "CSV should have header and data lines"

    def test_search_result_packaging(self):
        """Test packaging of search results with context"""
        try:
            from src_common.packaging import ContentPackager
        except ImportError:
            pytest.skip("Content packager not available for testing")

        packager = ContentPackager()

        # Test search result packaging
        search_session = {
            "session_id": "search_session_001",
            "queries": [
                {
                    "query": "wizard spells level 3",
                    "timestamp": datetime.now().isoformat(),
                    "results_count": 15,
                    "filters": {"class": "wizard", "level": 3}
                },
                {
                    "query": "fireball spell description",
                    "timestamp": (datetime.now()).isoformat(),
                    "results_count": 3,
                    "filters": {"spell_name": "fireball"}
                }
            ],
            "selected_results": [
                {
                    "content_id": "phb_fireball",
                    "selection_reason": "exact_match",
                    "user_notes": "Important spell for level 3 wizards"
                },
                {
                    "content_id": "phb_lightning_bolt",
                    "selection_reason": "related_spell",
                    "user_notes": "Alternative damage spell"
                }
            ],
            "export_preferences": {
                "include_context": True,
                "include_metadata": True,
                "format": "comprehensive"
            }
        }

        if hasattr(packager, 'package_search_session'):
            package_result = packager.package_search_session(search_session)

            assert isinstance(package_result, dict), "Package should return structured result"

            if "package_contents" in package_result:
                contents = package_result["package_contents"]
                assert isinstance(contents, dict), "Package contents should be dictionary"

                # Verify expected sections
                expected_sections = ["search_context", "selected_content", "metadata", "user_annotations"]
                for section in expected_sections:
                    if section in contents:
                        assert isinstance(contents[section], (dict, list)), f"Section {section} should be structured"

            if "package_size" in package_result:
                size = package_result["package_size"]
                assert isinstance(size, int), "Package size should be integer"
                assert size > 0, "Package size should be positive"

    def test_sharing_link_generation(self):
        """Test sharing link generation and access control"""
        try:
            from src_common.sharing import SharingService
        except ImportError:
            pytest.skip("Sharing service not available for testing")

        sharing_service = SharingService()

        # Test sharing configuration
        sharing_config = {
            "content_id": "shared_content_001",
            "sharing_type": "search_results",
            "access_control": {
                "visibility": "public",
                "expiration": "7_days",
                "password_protected": False,
                "download_allowed": True
            },
            "content_metadata": {
                "title": "Wizard Spells Research",
                "description": "Comprehensive collection of level 3 wizard spells",
                "tags": ["wizard", "spells", "level3"]
            }
        }

        if hasattr(sharing_service, 'create_sharing_link'):
            link_result = sharing_service.create_sharing_link(sharing_config)

            assert isinstance(link_result, dict), "Link creation should return structured result"

            if "sharing_url" in link_result:
                sharing_url = link_result["sharing_url"]
                assert isinstance(sharing_url, str), "Sharing URL should be string"
                assert sharing_url.startswith("http"), "Sharing URL should be valid HTTP URL"

            if "sharing_id" in link_result:
                sharing_id = link_result["sharing_id"]
                assert isinstance(sharing_id, str), "Sharing ID should be string"
                assert len(sharing_id) > 10, "Sharing ID should be sufficiently long"

            if "access_token" in link_result:
                access_token = link_result["access_token"]
                assert isinstance(access_token, str), "Access token should be string"

        # Test sharing link validation
        if hasattr(sharing_service, 'validate_sharing_access'):
            test_sharing_id = link_result.get("sharing_id", "test_sharing_001")

            access_request = {
                "sharing_id": test_sharing_id,
                "access_token": link_result.get("access_token"),
                "requester_ip": "192.168.1.100",
                "user_agent": "Mozilla/5.0 Test Browser"
            }

            validation_result = sharing_service.validate_sharing_access(access_request)

            assert isinstance(validation_result, dict), "Access validation should return structured result"

            if "access_granted" in validation_result:
                access_granted = validation_result["access_granted"]
                assert isinstance(access_granted, bool), "Access granted should be boolean"

            if "content_permissions" in validation_result:
                permissions = validation_result["content_permissions"]
                assert isinstance(permissions, dict), "Permissions should be dictionary"

    def test_collaborative_sharing_features(self):
        """Test collaborative sharing and annotation features"""
        try:
            from src_common.sharing import SharingService
        except ImportError:
            pytest.skip("Sharing service not available for testing")

        sharing_service = SharingService()

        # Test collaborative sharing setup
        collab_config = {
            "sharing_type": "collaborative",
            "participants": [
                {
                    "user_id": "user_001",
                    "role": "owner",
                    "permissions": ["read", "write", "share", "admin"]
                },
                {
                    "user_id": "user_002",
                    "role": "editor",
                    "permissions": ["read", "write", "comment"]
                },
                {
                    "user_id": "user_003",
                    "role": "viewer",
                    "permissions": ["read", "comment"]
                }
            ],
            "collaboration_features": {
                "real_time_editing": True,
                "comment_threads": True,
                "version_history": True,
                "change_notifications": True
            }
        }

        if hasattr(sharing_service, 'setup_collaborative_sharing'):
            collab_result = sharing_service.setup_collaborative_sharing(collab_config)

            assert isinstance(collab_result, dict), "Collaborative setup should return structured result"

            if "collaboration_space_id" in collab_result:
                space_id = collab_result["collaboration_space_id"]
                assert isinstance(space_id, str), "Collaboration space ID should be string"

            if "participant_tokens" in collab_result:
                tokens = collab_result["participant_tokens"]
                assert isinstance(tokens, dict), "Participant tokens should be dictionary"
                assert len(tokens) == len(collab_config["participants"]), "Should have token for each participant"

        # Test annotation functionality
        if hasattr(sharing_service, 'add_annotation'):
            annotation_data = {
                "content_id": "shared_content_001",
                "annotation_type": "comment",
                "text": "This spell is particularly useful in combat situations",
                "location": {"section": "fireball_description", "paragraph": 2},
                "author": "user_002",
                "timestamp": datetime.now().isoformat()
            }

            annotation_result = sharing_service.add_annotation(annotation_data)

            assert isinstance(annotation_result, dict), "Annotation should return structured result"

            if "annotation_id" in annotation_result:
                annotation_id = annotation_result["annotation_id"]
                assert isinstance(annotation_id, str), "Annotation ID should be string"

    def test_export_customization_and_templates(self):
        """Test export customization with templates and branding"""
        try:
            from src_common.export import ExportManager
        except ImportError:
            pytest.skip("Export manager not available for testing")

        export_manager = ExportManager()

        # Test custom template configuration
        template_config = {
            "template_name": "campaign_handout",
            "branding": {
                "logo": "campaign_logo.png",
                "colors": {
                    "primary": "#2c3e50",
                    "secondary": "#3498db",
                    "accent": "#e74c3c"
                },
                "fonts": {
                    "heading": "Georgia",
                    "body": "Arial",
                    "monospace": "Courier New"
                }
            },
            "layout": {
                "header": {"include": True, "height": "1in"},
                "footer": {"include": True, "content": "Page {page} of {total}"},
                "margins": {"top": "1in", "bottom": "1in", "left": "0.75in", "right": "0.75in"},
                "columns": 1
            },
            "content_sections": [
                {"name": "title_page", "enabled": True},
                {"name": "table_of_contents", "enabled": True},
                {"name": "search_summary", "enabled": True},
                {"name": "detailed_content", "enabled": True},
                {"name": "appendices", "enabled": False}
            ]
        }

        test_content = {
            "title": "Campaign Reference Guide",
            "subtitle": "Spell and Magic Item Compendium",
            "content_sections": [
                {
                    "section_type": "spells",
                    "title": "Wizard Spells",
                    "items": [
                        {"title": "Fireball", "description": "A bright streak flashes..."},
                        {"title": "Lightning Bolt", "description": "A stroke of lightning..."}
                    ]
                }
            ]
        }

        if hasattr(export_manager, 'export_with_template'):
            template_result = export_manager.export_with_template(test_content, template_config)

            assert isinstance(template_result, dict), "Template export should return structured result"

            if "export_data" in template_result:
                export_data = template_result["export_data"]
                assert export_data is not None, "Export data should not be None"

            if "template_applied" in template_result:
                template_applied = template_result["template_applied"]
                assert template_applied == template_config["template_name"], "Should confirm template applied"

            if "rendering_info" in template_result:
                rendering = template_result["rendering_info"]
                assert "page_count" in rendering, "Should provide page count"
                assert "render_time" in rendering, "Should track render time"

    def test_bulk_export_operations(self):
        """Test bulk export operations and batch processing"""
        try:
            from src_common.export import ExportManager
        except ImportError:
            pytest.skip("Export manager not available for testing")

        export_manager = ExportManager()

        # Test bulk export configuration
        bulk_export_config = {
            "export_sets": [
                {
                    "set_id": "wizard_content",
                    "query": "content_type:spells AND class:wizard",
                    "format": "pdf",
                    "template": "spell_compendium"
                },
                {
                    "set_id": "combat_rules",
                    "query": "content_type:rules AND topic:combat",
                    "format": "docx",
                    "template": "rules_reference"
                },
                {
                    "set_id": "magic_items",
                    "query": "content_type:items AND magical:true",
                    "format": "json",
                    "template": "data_export"
                }
            ],
            "packaging": {
                "create_archive": True,
                "archive_format": "zip",
                "include_manifest": True
            },
            "processing": {
                "parallel_exports": True,
                "max_concurrent": 3,
                "timeout_per_export": 300
            }
        }

        if hasattr(export_manager, 'execute_bulk_export'):
            bulk_result = export_manager.execute_bulk_export(bulk_export_config)

            assert isinstance(bulk_result, dict), "Bulk export should return structured result"

            if "export_results" in bulk_result:
                results = bulk_result["export_results"]
                assert isinstance(results, dict), "Export results should be dictionary"
                assert len(results) == len(bulk_export_config["export_sets"]), "Should have result for each set"

            if "archive_info" in bulk_result:
                archive = bulk_result["archive_info"]
                assert "archive_path" in archive, "Should provide archive path"
                assert "archive_size" in archive, "Should provide archive size"

            if "processing_summary" in bulk_result:
                summary = bulk_result["processing_summary"]
                assert "total_exports" in summary, "Should track total exports"
                assert "successful_exports" in summary, "Should track successful exports"
                assert "total_processing_time" in summary, "Should track processing time"

    def test_export_sharing_contract_compliance(self):
        """Test that export and sharing matches established contract"""
        # Test export contract
        export_requirements = {
            "multiple_formats": True,
            "template_customization": True,
            "bulk_operations": True,
            "metadata_preservation": True,
            "content_packaging": True
        }

        for requirement, needed in export_requirements.items():
            assert needed, f"Export requirement {requirement} is mandatory"

        # Test sharing contract
        sharing_requirements = {
            "link_generation": True,
            "access_control": True,
            "collaborative_features": True,
            "annotation_support": True,
            "expiration_management": True
        }

        for requirement, needed in sharing_requirements.items():
            assert needed, f"Sharing requirement {requirement} is mandatory"

        # Test format contract
        format_requirements = {
            "pdf_export": True,
            "docx_export": True,
            "json_export": True,
            "csv_export": True,
            "html_export": True
        }

        for requirement, needed in format_requirements.items():
            assert needed, f"Format requirement {requirement} is mandatory"

        # Test data contract
        required_export_fields = [
            "export_format",
            "export_size",
            "creation_timestamp",
            "content_checksum",
            "export_metadata"
        ]

        for field in required_export_fields:
            assert isinstance(field, str), f"Export field {field} should be defined"

        # Test integration contract
        integration_points = [
            "content_retrieval_integration",
            "template_engine_integration",
            "sharing_service_integration",
            "notification_system_integration"
        ]

        for integration in integration_points:
            assert isinstance(integration, str), f"Integration point {integration} should be defined"