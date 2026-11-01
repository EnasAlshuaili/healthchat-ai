"""HealthChat AI HTTP API, phase A: mock-only (D-19, docs/API_CONTRACT.md).

A thin FastAPI layer. Every reply is a fixed mock or input-check template
(`is_mock` is always True). Nothing here imports the Safety & Scope Router, the
topic matcher, retrieval, curated content, or the dataset, and nothing calls an
external service.
"""
