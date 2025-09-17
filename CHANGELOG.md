# Changelog

All notable changes to the TTRPG Center project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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