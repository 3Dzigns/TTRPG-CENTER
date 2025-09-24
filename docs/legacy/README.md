# Legacy System Archives

This directory contains archived documentation from the pre-MVP v2 system that has been replaced by the new Pass 0→G pipeline architecture.

## Archived Content

### phases-old-system/
Contains the original Phase 0-7 system documentation that was used before the MVP v2 rewrite. This system has been completely replaced by the new:

- **Pass 0**: Preflight & De-dup
- **Pass A**: TOC & Dictionary Seed
- **Pass B**: Fast Split (≤10 MB parts)
- **Pass C**: Extraction (Unstructured.io)
- **Pass D**: Normalize + Embeddings (Haystack)
- **Pass E**: Graph Compile (LlamaIndex)
- **Pass F**: Validation & Manifest
- **Pass G**: HGRN Consistency Check

### Why Archived?
The Phase 0-7 system was replaced in favor of:
1. **Environment Isolation**: Strict dev/test/prod separation
2. **Microservices Architecture**: Service-oriented design with proper boundaries
3. **Pass-based Pipeline**: More focused processing stages
4. **External Test Execution**: Docker-based isolated testing
5. **Structured Logging**: MVP v2 compliant JSON logging schema

## Current System
For current system documentation, see:
- `../README.md` - Main project documentation
- `../MVP-Version-2/` - Requirements and specifications
- `../CONTRIBUTING.md` - Development guidelines
- `../SECURITY.md` - Security policy

## Historical Value
This archived content is preserved for:
- Understanding system evolution
- Learning from previous architectural decisions
- Reference for migration questions
- Historical context for team members

**Date Archived**: September 24, 2025
**Reason**: MVP v2 system implementation completed