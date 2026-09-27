"""Selective Edge Traversal Engine for LegalPilot-VN Knowledge Graph.

Implements temporal-guided graph traversal over Vietnamese legal statutes,
pruning expired, future, or superseded legal provisions while resolving
cross-statutory amendments (e.g. Decree 70/2023 amending Decree 152/2020).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.core.exceptions import KnowledgeBaseError
from src.core.logger import get_logger
from src.knowledge.neo4j_client import Neo4jClient

logger = get_logger(__name__)


@dataclass
class TraversalContext:
    """Configuration parameters for a selective traversal query."""

    reference_date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    max_hops: int = 2
    max_nodes: int = 10
    allowed_rel_types: list[str] = field(
        default_factory=lambda: ["AMENDS", "GUIDES", "REFERS_TO", "CONTAINS", "SUPERSEDES"]
    )
    strict_temporal: bool = True


@dataclass
class TraversalResult:
    """Structured result containing active provisions, amendment traces, and pruning metrics."""

    seed_doc_id: str
    reference_date: str
    active_articles: list[dict[str, Any]] = field(default_factory=list)
    amendment_chains: list[dict[str, Any]] = field(default_factory=list)
    repealed_provisions: list[dict[str, Any]] = field(default_factory=list)
    traversed_nodes_count: int = 0
    pruned_nodes_count: int = 0

    @property
    def noise_reduction_ratio(self) -> float:
        """Calculates percentage of graph noise pruned by the selective engine."""
        total = self.traversed_nodes_count + self.pruned_nodes_count
        if total == 0:
            return 0.0
        return round(self.pruned_nodes_count / total, 4)


class SelectiveTraversalEngine:
    """Engine executing temporal-aware and directional traversal on Neo4j."""

    def __init__(self, neo4j_client: Neo4jClient | None = None):
        """Initializes traversal engine with active Neo4j client."""
        self.client = neo4j_client or Neo4jClient()

    def traverse(
        self,
        seed_doc_id: str,
        context: TraversalContext | None = None,
    ) -> TraversalResult:
        """Executes selective edge traversal starting from seed_doc_id.

        Prunes:
        1. Documents whose effective_date > reference_date (not yet in force).
        2. Documents whose expiration_date <= reference_date (expired).
        3. Documents whose status == 'expired'.
        4. Clauses explicitly repealed by newer amending statutes.
        """
        ctx = context or TraversalContext()
        logger.info(
            "Executing selective traversal for '%s' at reference date: %s",
            seed_doc_id,
            ctx.reference_date,
        )

        # 1. Fetch seed document hierarchy
        seed_doc = self.client.get_document_by_id(seed_doc_id)
        if not seed_doc:
            raise KnowledgeBaseError(f"Seed document not found in graph: {seed_doc_id}")

        traversed_count = 1
        pruned_count = 0

        # Check temporal validity of seed
        is_seed_active = self._is_active(
            seed_doc.get("effective_date"),
            seed_doc.get("expiration_date"),
            seed_doc.get("status", "in_force"),
            ctx.reference_date,
        )
        if not is_seed_active and ctx.strict_temporal:
            logger.warning(
                "Seed document '%s' is not active at %s", seed_doc_id, ctx.reference_date
            )
            pruned_count += 1
            return TraversalResult(
                seed_doc_id=seed_doc_id,
                reference_date=ctx.reference_date,
                traversed_nodes_count=traversed_count,
                pruned_nodes_count=pruned_count,
            )

        # 2. Retrieve amendment and related documents
        rel_query = """
        MATCH (seed:Document {doc_id: $seed_doc_id})
        OPTIONAL MATCH (amender:Document)-[r_amend:AMENDS]->(seed)
        OPTIONAL MATCH (seed)-[r_guide:GUIDES]->(guided:Document)
        OPTIONAL MATCH (seed)-[r_ref:REFERS_TO]->(ref:Document)
        OPTIONAL MATCH (repealer:Document)-[r_rep:SUPERSEDES]->(seed)
        RETURN
            collect(DISTINCT {node: amender, rel: 'AMENDS', props: properties(r_amend)}) as amenders,
            collect(DISTINCT {node: guided, rel: 'GUIDES', props: properties(r_guide)}) as guided_docs,
            collect(DISTINCT {node: ref, rel: 'REFERS_TO', props: properties(r_ref)}) as ref_docs,
            collect(DISTINCT {node: repealer, rel: 'SUPERSEDES', props: properties(r_rep)}) as repealers
        """
        rel_res = self.client.execute_query(rel_query, {"seed_doc_id": seed_doc_id})
        amenders = []
        repealers = []

        if rel_res:
            raw_amenders = [item for item in rel_res[0].get("amenders", []) if item.get("node")]
            raw_repealers = [item for item in rel_res[0].get("repealers", []) if item.get("node")]

            # Evaluate each neighbor temporally
            for item in raw_amenders:
                node = item["node"]
                traversed_count += 1
                if self._is_active(
                    node.get("effective_date"),
                    node.get("expiration_date"),
                    node.get("status", "in_force"),
                    ctx.reference_date,
                ):
                    amenders.append(item)
                else:
                    logger.debug("Pruning inactive amending document: %s", node.get("doc_id"))
                    pruned_count += 1

            for item in raw_repealers:
                node = item["node"]
                traversed_count += 1
                if self._is_active(
                    node.get("effective_date"),
                    node.get("expiration_date"),
                    node.get("status", "in_force"),
                    ctx.reference_date,
                ):
                    repealers.append(item)
                else:
                    logger.debug("Pruning inactive repealing document: %s", node.get("doc_id"))
                    pruned_count += 1

        # 3. Construct active articles and resolve amendments
        active_articles: list[dict[str, Any]] = []
        amendment_chains: list[dict[str, Any]] = []
        repealed_provisions: list[dict[str, Any]] = []

        # Record repeals from SUPERSEDES
        for rep in repealers:
            r_props = rep.get("props", {})
            repealed_provisions.append(
                {
                    "repealer_doc_id": rep["node"].get("doc_id"),
                    "scope": r_props.get("scope", "Entire document"),
                    "effective_date": rep["node"].get("effective_date"),
                }
            )

        # Map active articles from seed
        for art in seed_doc.get("articles", []):
            art_id = art.get("article_id")
            art_num = art.get("article_number")
            art_title = art.get("title")
            art_content = art.get("content")

            # Check if this article was amended by any active amender
            active_version = {
                "article_id": art_id,
                "article_number": art_num,
                "title": art_title,
                "content": art_content,
                "governing_doc_id": seed_doc_id,
                "is_amended": False,
                "amended_by": None,
                "amendment_notes": None,
            }

            for amender in amenders:
                amender_node = amender["node"]
                amender_id = amender_node.get("doc_id")
                # Look for matching articles in amender document
                amender_details = self.client.get_document_by_id(amender_id)
                if amender_details:
                    for a_art in amender_details.get("articles", []):
                        # If amender article mentions modifying this article
                        if f"Điều {art_num}" in a_art.get(
                            "content", ""
                        ) or f"Điều {art_num}" in a_art.get("title", ""):
                            active_version["is_amended"] = True
                            active_version["amended_by"] = amender_id
                            active_version["amendment_notes"] = (
                                f"Amended by {amender_id} ({a_art.get('title')})"
                            )
                            active_version["content"] = a_art.get("content")
                            active_version["governing_doc_id"] = amender_id

                            amendment_chains.append(
                                {
                                    "original_article_id": art_id,
                                    "original_doc_id": seed_doc_id,
                                    "amended_by_doc_id": amender_id,
                                    "amender_article_id": a_art.get("article_id"),
                                    "effective_date": amender_node.get("effective_date"),
                                }
                            )
                            break

            active_articles.append(active_version)

        # Check if any article is marked as repealed
        filtered_active_articles = []
        for art in active_articles:
            art_num = art["article_number"]
            # Check against repealed provisions
            is_repealed = any(
                f"Điều {art_num}" in rep.get("scope", "") for rep in repealed_provisions
            )
            if is_repealed:
                logger.info("Pruning repealed article: Điều %s of %s", art_num, seed_doc_id)
                pruned_count += 1
            else:
                filtered_active_articles.append(art)

        result = TraversalResult(
            seed_doc_id=seed_doc_id,
            reference_date=ctx.reference_date,
            active_articles=filtered_active_articles,
            amendment_chains=amendment_chains,
            repealed_provisions=repealed_provisions,
            traversed_nodes_count=traversed_count,
            pruned_nodes_count=pruned_count,
        )

        logger.info(
            "Traversal complete for '%s': %d active articles, %d amendments, %d pruned (ratio: %.2f)",
            seed_doc_id,
            len(result.active_articles),
            len(result.amendment_chains),
            result.pruned_nodes_count,
            result.noise_reduction_ratio,
        )
        return result

    def synthesize_active_context(self, result: TraversalResult) -> str:
        """Formats the traversal result into clean, citation-grounded Markdown for LLM synthesis."""
        lines = [
            f"# Active Statutory Context: {result.seed_doc_id}",
            f"**Reference Date**: {result.reference_date}",
            f"**Selective Pruning**: {result.pruned_nodes_count} obsolete/future nodes pruned (Noise Reduction: {result.noise_reduction_ratio * 100:.1f}%)",
            "",
        ]

        if result.amendment_chains:
            lines.append("## Active Amendment Overrides")
            for chain in result.amendment_chains:
                lines.append(
                    f"- `{chain['original_article_id']}` superseded by **{chain['amended_by_doc_id']}** (Effective: {chain['effective_date']})"
                )
            lines.append("")

        if result.repealed_provisions:
            lines.append("## Repealed Provisions")
            for rep in result.repealed_provisions:
                lines.append(
                    f"- Repealed by **{rep['repealer_doc_id']}**: {rep['scope']} (Effective: {rep['effective_date']})"
                )
            lines.append("")

        lines.append("## Governing Articles")
        for art in result.active_articles:
            status_tag = f"[AMENDED by {art['amended_by']}]" if art["is_amended"] else "[IN FORCE]"
            lines.append(f"### Điều {art['article_number']}. {art['title']} {status_tag}")
            lines.append(f"*Governing Document: {art['governing_doc_id']}*")
            lines.append("")
            lines.append(art["content"])
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _is_active(
        effective_date: str | None,
        expiration_date: str | None,
        status: str,
        reference_date: str,
    ) -> bool:
        """Determines if a document or provision is active on reference_date."""
        if status == "expired":
            return False

        if effective_date and effective_date > reference_date:
            return False  # Not yet effective

        return not bool(expiration_date and expiration_date <= reference_date)
