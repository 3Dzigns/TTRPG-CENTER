# Changelog

All notable changes to the TTRPG Center project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
- Ingestion pipeline enhanced with Pass D HGRN validation for comprehensive quality assurance
- Admin interface expanded with HGRN recommendation management capabilities
- Model routing enhanced to support HGRN validation intent classification
- Environment configuration extended with HGRN-specific settings and controls

- Dictionary management system migrated from file-based storage to MongoDB backend
- Admin UI dictionary interface enhanced with MongoDB connection status indicators
- Performance optimized with 15+ specialized MongoDB indexes for sub-1.5s queries
- Error handling improved with circuit breaker pattern and graceful degradation

### Technical Details
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