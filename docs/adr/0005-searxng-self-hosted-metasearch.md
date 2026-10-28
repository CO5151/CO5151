# ADR-0005: Self-Hosted SearXNG for External Web Legal Grounding

* **Status**: Accepted
* **Date**: 2026-10-25
* **Authors**: LegalPilot-VN Engineering Team

---

## Context

Legal AI agents in LegalPilot-VN frequently require external retrieval to discover recent legal circulars, decrees, and gazette notices hosted across official governmental portals (e.g., `vbpl.vn`, `chinhphu.vn`, `moj.gov.vn`, `sbv.gov.vn`).

However, several challenges arise with traditional web search integrations:
1. **Recurring API Costs**: Commercial search APIs (such as Google Custom Search, Bing Web Search, Tavily, or SerpAPI) charge per query, incurring unpredictable operational expenses during large benchmark evaluations or multi-turn agent investigations.
2. **Data Privacy & Leakage**: Enterprise legal queries sent to third-party commercial search providers may expose proprietary compliance concerns or confidential client contexts.
3. **Anti-Scraping Defenses**: Direct programmatic scraping of official portals (`vbpl.vn`, `chinhphu.vn`) often encounters HTTP 403 Forbidden errors or anti-bot challenge walls, rendering standalone HTTP client scrapers brittle.
4. **Result Quality & Hallucination Risk**: Unconstrained web searches often surface third-party commercial aggregators or SEO-driven advisory blogs that contain outdated or inaccurate summaries of statutory articles.

---

## Decision

We adopt **SearXNG** as the dedicated, self-hosted metasearch engine for LegalPilot-VN, bundled into the core local container stack alongside Neo4j and Qdrant.

```
       [User / Orchestrator Agent]
                    │
                    ▼
       [Web Search Tool (src/tools/web_search.py)]
                    │
         (Domain Whitelist Filter)
                    │
                    ▼
  [SearXNG Container (legalpilot-searxng:8080)]
   ├── Metasearch Aggregation (Google, Bing, DDG, etc.)
   ├── Privacy-Preserving Proxying (No user tracking)
   └── JSON Search Endpoint (/search?format=json)
                    │
                    ▼
  [Official Government Portals (vbpl.vn, chinhphu.vn, moj.gov.vn)]
```

### Key Implementation Principles

1. **Dockerized Deployment**:
   * Defined as `legalpilot-searxng` in [`docker-compose.yml`](../../docker-compose.yml).
   * Configured via [`configs/searxng/settings.yml`](../../configs/searxng/settings.yml) with JSON output enabled and secret key persistence.
2. **Domain Whitelisting**:
   * Search requests executed via [`src/tools/web_search.py`](../../src/tools/web_search.py) are strictly filtered against `DEFAULT_ALLOWED_DOMAINS` (`vbpl.vn`, `vanban.chinhphu.vn`, `congbao.chinhphu.vn`, `chinhphu.vn`, `quochoi.vn`, `moj.gov.vn`, `sbv.gov.vn`).
   * Non-official or secondary commentary sites are discarded and logged under `blocked_domains`.
3. **Strict Separation of Concerns (Discovery vs. Validity Oracle)**:
   * External web findings are stored under `web_findings` with `verified: False` for contextual reference only.
   * Web search is explicitly **forbidden** from acting as a legal validity oracle; the validity and temporal in-force status of statutory clauses are strictly evaluated by the Neo4j Property Graph and validity checker audit path.

---

## Consequences

### Positive
* **Zero Variable Costs**: No paid API keys or subscription fees required for web retrieval.
* **Privacy & Isolation**: Legal search queries remain internal or anonymized; no search profiles or telemetry are sent to proprietary search ad networks.
* **Engine Aggregation & Resilience**: By aggregating across multiple upstream search engines simultaneously, SearXNG avoids single-point-of-failure rate-limits and CAPTCHA blocks.
* **Seamless Local Developer Experience**: Starts with a single command (`docker compose up -d searxng`) with predictable port mapping (`8080`).

### Negative / Trade-offs
* **Container Resource Footprint**: Running SearXNG requires Docker/Colima and allocates ~100–200MB of resident system memory.
* **Upstream Rate Limiting**: If high volumes of concurrent automated queries are fired against SearXNG without delay, some upstream engines may intermittently challenge or throttle the container IP, requiring upstream engine rotation or fallback query strategies.
