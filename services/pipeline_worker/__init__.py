"""
Pipeline Worker Microservice

A dedicated microservice for managing the 7-pass ingestion pipeline with
separate worker pools per pass (A-G).

Features:
- Independent pass execution capability
- Worker pool management (2 workers per pass by default)
- Priority job queue
- Three trigger modes: nightly, ad-hoc, selective
- Real-time metrics and monitoring
"""

__version__ = "1.0.0"