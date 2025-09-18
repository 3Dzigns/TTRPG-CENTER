# Changelog

All notable changes to the TTRPG Center project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **FR-030 Favicon System** - Comprehensive favicon support for professional brand identity
  - D20-themed favicon design representing TTRPG gaming core mechanics
  - Multi-format favicon support (ICO, PNG, SVG) for all browsers and devices
  - Progressive Web App manifest for mobile home screen icons
  - Apple Touch Icon and Android Chrome icons for mobile platforms
  - Comprehensive meta tags integrated across all HTML templates
  - Optimized file sizes for fast loading with professional visual identity

- **FR-029 Delta Refresh System** - Intelligent incremental document processing with SHA-based change detection
  - Complete delta refresh orchestration system with granular page and section-level change detection
  - SHA-256 content fingerprinting for reliable change detection and selective pipeline updates
  - IncrementalIngestionManager with background job management and concurrent processing prevention
  - DeltaTracker for audit trail, session management, and rollback capabilities
  - Comprehensive test suite with 44 passing tests covering all delta refresh components
  - Performance optimization targeting 80%+ reduction in processing time for incremental updates
  - Integration with existing 3-pass ingestion pipeline (unstructured.io → Haystack → LlamaIndex)
  - Configurable similarity thresholds and intelligent fallback to full processing

- **FR-031 Cassandra Vector Store (DEV/CI)** - Local vector storage now runs on Apache Cassandra via Docker (replaces Astra dependency)
  - Added pluggable vector store abstraction with Cassandra and Astra implementations
  - Updated ingestion passes, admin/dashboard endpoints, and retriever to use the new backend
  - Docker Compose now provisions a cassandra:5 service with health checks and env wiring
  - Added cassandra-driver dependency and configuration/env templates for dev/test pipelines
  - Authored Cassandra setup runbook and docs updates covering feature flag, schema, and troubleshooting

- **FR-023 Persona Testing Framework** - Complete implementation of persona-aware testing and validation system
  - Comprehensive persona management system with 7+ predefined user types and experience levels
  - Query-time persona context extraction and response appropriateness validation
  - Integration with AEHRL evaluation system for persona-specific quality assessment
  - Persona-aware response validation measuring appropriateness, detail level match, and user satisfaction
  - Real-time persona metrics tracking with performance analytics and alerting
  - Advanced admin UI for persona management, metrics visualization, and test scenario execution
  - RESTful API endpoints for persona profiles, metrics, alerts, and test scenario management
  - Comprehensive test suite with unit and functional coverage for all persona components
  - Environment-controlled feature flags with graceful degradation on persona service failures
  - Legacy persona integration supporting existing Personas/ directory markdown files

- **FR-022 AEHRL Integration** - Complete implementation of Automated Evaluation & Hallucination Reduction Layer
  - Query-time hallucination detection system with fact extraction and evidence gathering
  - Ingestion-time quality assurance layer integrated with HGRN validation pipeline
  - Intelligent fact claim extraction using NLP patterns for D&D-specific content (damage, AC, hit points)
  - Support evidence gathering from retrieved chunks, graph context, and dictionary entries
  - Correction recommendation system with confidence scoring and automated suggestions
  - Comprehensive admin UI for AEHRL management with filtering, sorting, and workflow controls
  - RESTful API endpoints for correction accept/reject operations with audit trails
  - Real-time metrics tracking with configurable alerting for hallucination rate monitoring
  - Environment-controlled feature flags with graceful degradation on AEHRL service failures
  - Comprehensive test coverage including unit and functional end-to-end tests

- **FR-021 HGRN Integration** - Complete implementation of Hierarchical Graph Recurrent Network validation as Pass D
  - HGRN validation pipeline integrated as Pass D in ingestion workflow
  - Intelligent recommendation system for dictionary metadata, graph integrity, and chunk artifacts
  - Comprehensive admin UI for HGRN recommendation management with filtering and workflow controls
  - RESTful API endpoints for recommendation accept/reject operations
  - Environment-controlled feature flags with graceful degradation when HGRN package unavailable
  - Mock implementation ensuring system stability across all environments
  - Model routing integration for HGRN validation intent classification

- **FR-015 MongoDB Dictionary Integration** - Complete implementation of MongoDB-backed dictionary management system
  - High-performance MongoDB service with optimized indexing for ≤1.5s search requirement
  - Circuit breaker pattern for resilient error handling and automatic fallback
  - Admin UI enhancements with real-time MongoDB connection monitoring
  - Unified dictionary model supporting seamless data transformation
  - Comprehensive integration tests validating MongoDB query operations
  - Health monitoring and diagnostic endpoints for operational visibility

### Changed
- Query processing pipeline enhanced with persona-aware evaluation and response validation
- Orchestrator service extended with persona context extraction and appropriateness scoring
- Admin interface expanded with persona testing management, metrics visualization, and test execution
- AEHRL evaluation system enhanced to consider persona context for improved accuracy
- Environment configuration extended with persona testing framework settings and thresholds

- Query processing pipeline enhanced with AEHRL hallucination detection and fact verification
- Ingestion pipeline extended with AEHRL quality assurance layer working alongside HGRN validation
- Admin interface expanded with comprehensive AEHRL management capabilities and metrics dashboard
- Orchestrator service enhanced with query-time AEHRL evaluation and confidence scoring
- Environment configuration extended with AEHRL-specific settings and processing timeouts

- Ingestion pipeline enhanced with Pass D HGRN validation for comprehensive quality assurance
- Admin interface expanded with HGRN recommendation management capabilities
- Model routing enhanced to support HGRN validation intent classification
- Environment configuration extended with HGRN-specific settings and controls

- Dictionary management system migrated from file-based storage to MongoDB backend
- Admin UI dictionary interface enhanced with MongoDB connection status indicators
- Performance optimized with 15+ specialized MongoDB indexes for sub-1.5s queries
- Error handling improved with circuit breaker pattern and graceful degradation

### Technical Details
- Persona testing framework with comprehensive user modeling and context extraction
- Response appropriateness validation using persona-specific criteria and scoring algorithms
- Integration with AEHRL evaluation system for enhanced persona-aware quality assessment
- Real-time metrics tracking with persona-specific performance analytics and alerting
- Admin UI with interactive persona management, metrics visualization, and test execution
- RESTful API design for persona profiles, scenarios, metrics, and administrative operations
- Comprehensive data models for persona profiles, contexts, metrics, and test scenarios

- AEHRL integration with dual evaluation modes (query-time and ingestion-time)
- Fact extraction system with pattern-based D&D content recognition
- Evidence gathering from multiple sources (chunks, graph, dictionary)
- Correction recommendation engine with confidence-based suggestion algorithms
- Metrics tracking with JSON persistence and configurable alerting thresholds
- Admin UI with AJAX-based API integration and real-time status updates
- Comprehensive data models for hallucination flags, fact claims, and correction workflows

- HGRN integration with mock implementation for graceful degradation
- Pass D validation pipeline with configurable confidence thresholds
- RESTful API design for recommendation workflow management
- Environment-specific HGRN configuration with feature flag controls
- Comprehensive data models for validation reports and recommendations

- MongoDB collection design with optimized indexing strategy
- Circuit breaker implementation with configurable failure thresholds
- Fallback mechanisms maintaining system availability during MongoDB outages
- Comprehensive logging and monitoring for operational diagnostics

## [Previous Releases]
<!-- Future releases will be documented here -->