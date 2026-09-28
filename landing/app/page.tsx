import Image from "next/image";
import {
  IconScale,
  IconShieldCheck,
  IconGitFork,
  IconClock,
  IconCheck,
  IconX,
  IconArrowRight,
  IconFileText,
  IconCpu,
  IconDatabase,
  IconSearch,
  IconLock,
  IconTerminal,
  IconCode,
  IconBook,
  IconLayersLinked,
  IconSparkles,
} from "@tabler/icons-react";

const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";

export default function Home() {
  return (
    <div className="min-h-screen bg-[#09090b] text-zinc-100 selection:bg-emerald-950 selection:text-emerald-400">
      {/* Navigation */}
      <header className="sticky top-0 z-50 border-b border-zinc-800/80 bg-[#09090b]/90 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-md border border-zinc-700 bg-zinc-900 text-emerald-400">
              <IconScale size={18} strokeWidth={2} />
            </div>
            <span className="font-mono text-sm font-semibold tracking-tight text-zinc-100">
              LegalPilot-VN
            </span>
          </div>

          <nav className="hidden items-center gap-6 text-xs text-zinc-400 md:flex">
            <a href="#problem" className="transition hover:text-zinc-200">
              Problem
            </a>
            <a href="#architecture" className="transition hover:text-zinc-200">
              Architecture
            </a>
            <a href="#traversal" className="transition hover:text-zinc-200">
              Selective Traversal
            </a>
            <a href="#ingestion" className="transition hover:text-zinc-200">
              Hybrid Ingestion
            </a>
            <a href="#auditor" className="transition hover:text-zinc-200">
              Claim Auditor
            </a>
            <a href="#threat-model" className="transition hover:text-zinc-200">
              Security
            </a>
            <a href="#adrs" className="transition hover:text-zinc-200">
              ADRs & Docs
            </a>
          </nav>

          <div className="flex items-center gap-3">
            <a
              href="https://github.com/DangLamTung/CO5151"
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-9 items-center rounded-md border border-zinc-800 bg-zinc-900 px-3 text-xs font-medium text-zinc-300 transition hover:border-zinc-700 hover:text-white active:scale-[0.98]"
            >
              GitHub
            </a>
            <a
              href="https://github.com/DangLamTung/CO5151/tree/main/docs"
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-9 items-center rounded-md bg-emerald-500 px-3.5 text-xs font-medium text-black transition hover:bg-emerald-400 active:scale-[0.98]"
            >
              Documentation
            </a>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6">
        {/* Section 1: Hero Section (Layout Family: Split 50/50) */}
        <section className="flex min-h-[calc(100dvh-4rem)] flex-col justify-center py-12 lg:py-16">
          <div className="grid grid-cols-1 items-center gap-12 lg:grid-cols-12">
            <div className="lg:col-span-7">
              {/* Eyebrow 1 of 2 */}
              <div className="mb-4 inline-flex items-center gap-2 rounded-md border border-emerald-950 bg-emerald-950/30 px-2.5 py-1 font-mono text-[11px] uppercase tracking-wider text-emerald-400">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                CO5151 Research Deliverable
              </div>

              <h1 className="text-4xl font-semibold tracking-tight text-zinc-100 sm:text-5xl lg:text-6xl leading-[1.1]">
                Autonomous Legal Compliance for Vietnamese Statutory Law
              </h1>

              <p className="mt-5 max-w-[65ch] text-base leading-relaxed text-zinc-400 sm:text-lg">
                Multi-agent RAG resolving cross-statutory amendments, verifying temporal gazette validity, and auditing compliance with zero hallucination.
              </p>

              <div className="mt-8 flex flex-wrap items-center gap-4">
                <a
                  href="#architecture"
                  className="inline-flex h-11 items-center rounded-md bg-emerald-500 px-5 text-sm font-semibold text-black transition hover:bg-emerald-400 active:scale-[0.98]"
                >
                  Explore Architecture
                </a>
                <a
                  href="https://github.com/DangLamTung/CO5151/tree/main/docs"
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex h-11 items-center gap-2 rounded-md border border-zinc-800 bg-zinc-900/80 px-5 text-sm font-medium text-zinc-300 transition hover:border-zinc-700 hover:text-white active:scale-[0.98]"
                >
                  <IconBook size={16} />
                  Read Documentation
                </a>
              </div>
            </div>

            <div className="lg:col-span-5">
              <div className="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/50 shadow-2xl">
                <div className="flex items-center justify-between border-b border-zinc-800 bg-zinc-900/80 px-4 py-2.5">
                  <div className="flex items-center gap-2 font-mono text-xs text-zinc-400">
                    <IconTerminal size={14} className="text-emerald-400" />
                    <span>multi-agent-orchestrator.log</span>
                  </div>
                  <span className="rounded bg-emerald-950 px-1.5 py-0.5 font-mono text-[10px] text-emerald-400">
                    ONLINE
                  </span>
                </div>
                <div className="relative aspect-video w-full bg-zinc-950">
                  <Image
                    src={`${basePath}/images/hero-agent-trace.jpg`}
                    alt="Multi-agent legal compliance execution visualization"
                    fill
                    className="object-cover"
                    priority
                  />
                </div>
                <div className="border-t border-zinc-800 bg-zinc-950/80 p-3 font-mono text-xs text-zinc-400">
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-500">Target: Decree 152/2020 & Decree 70/2023</span>
                    <span className="text-emerald-400">Claims Grounded: 100%</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Section 2: Problem Context (Layout Family: Asymmetric Data Grid) */}
        <section id="problem" className="border-t border-zinc-800/80 py-20">
          <div className="max-w-3xl">
            <h2 className="text-3xl font-semibold tracking-tight text-zinc-100 sm:text-4xl">
              Statutory reasoning is not a keyword search problem
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-zinc-400 sm:text-base">
              Vietnamese legal applicability depends on statutory hierarchy, directional cross-references, and temporal validity. Standard single-pass RAG exhibits three structural failure modes.
            </p>
          </div>

          <div className="mt-12 grid grid-cols-1 gap-6 md:grid-cols-3">
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-zinc-700 bg-zinc-900 text-red-400">
                <IconGitFork size={20} />
              </div>
              <h3 className="mt-4 text-base font-semibold text-zinc-100">Context Dilution</h3>
              <p className="mt-2 text-xs leading-relaxed text-zinc-400">
                In SBV-LawGraph, mechanical 1-hop expansion drops Precision@2 to 0.38 because omnibus circulars amend dozens of unrelated articles, injecting over 60% noise into the prompt.
              </p>
              <div className="mt-4 rounded border border-zinc-800 bg-zinc-950 p-2 font-mono text-[11px] text-red-400">
                Precision@2: 0.38 (Baseline)
              </div>
            </div>

            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-zinc-700 bg-zinc-900 text-amber-400">
                <IconClock size={20} />
              </div>
              <h3 className="mt-4 text-base font-semibold text-zinc-100">Temporal Inconsistency</h3>
              <p className="mt-2 text-xs leading-relaxed text-zinc-400">
                Offline vector indices cannot determine whether a cited decree was repealed, replaced, or not yet in force at the transaction date, resulting in invalid legal citations.
              </p>
              <div className="mt-4 rounded border border-zinc-800 bg-zinc-950 p-2 font-mono text-[11px] text-amber-400">
                Status: Obsolete Statute Risk
              </div>
            </div>

            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-zinc-700 bg-zinc-900 text-emerald-400">
                <IconShieldCheck size={20} />
              </div>
              <h3 className="mt-4 text-base font-semibold text-zinc-100">Lack of Claim Auditing</h3>
              <p className="mt-2 text-xs leading-relaxed text-zinc-400">
                Standard RAG pipelines pass LLM generation directly to the user without verifying individual propositions against source articles, leading to hallucinated regulatory thresholds.
              </p>
              <div className="mt-4 rounded border border-zinc-800 bg-zinc-950 p-2 font-mono text-[11px] text-emerald-400">
                Verification: Zero Gate Checks
              </div>
            </div>
          </div>
        </section>

        {/* Section 3: Multi-Agent Architecture (Layout Family: Vertical Process Stepper) */}
        <section id="architecture" className="border-t border-zinc-800/80 py-20">
          <div className="max-w-3xl">
            <h2 className="text-3xl font-semibold tracking-tight text-zinc-100 sm:text-4xl">
              Five specialized agents under Google ADK supervisor orchestration
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-zinc-400 sm:text-base">
              Built on Google Agent Development Kit with shared execution state. Tasks are dynamically routed based on statutory ambiguity, factual completeness, and verification feedback.
            </p>
          </div>

          <div className="mt-12 space-y-4">
            <div className="flex flex-col gap-4 rounded-xl border border-zinc-800 bg-zinc-900/30 p-5 md:flex-row md:items-center md:justify-between">
              <div className="flex items-start gap-4">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-emerald-900/50 bg-emerald-950/40 text-emerald-400">
                  <IconCpu size={18} />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-zinc-100">1. Lead Counsel Agent (Supervisor)</h3>
                    <span className="rounded bg-zinc-800 px-2 py-0.5 font-mono text-[10px] text-zinc-300">Google ADK</span>
                  </div>
                  <p className="mt-1 text-xs text-zinc-400">
                    Analyzes user compliance inquiries, decomposes multi-faceted questions into specialist tasks, and synthesizes verified statutory counsel.
                  </p>
                </div>
              </div>
              <div className="shrink-0 font-mono text-xs text-zinc-500">Dynamic Planning</div>
            </div>

            <div className="flex flex-col gap-4 rounded-xl border border-zinc-800 bg-zinc-900/30 p-5 md:flex-row md:items-center md:justify-between">
              <div className="flex items-start gap-4">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-zinc-700 bg-zinc-800 text-zinc-200">
                  <IconDatabase size={18} />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-zinc-100">2. Legal Research Agent</h3>
                    <span className="rounded bg-zinc-800 px-2 py-0.5 font-mono text-[10px] text-zinc-300">Neo4j + Qdrant</span>
                  </div>
                  <p className="mt-1 text-xs text-zinc-400">
                    Queries the dual knowledge layer to retrieve contextualized legal chunks and traverses AMENDS, SUPERSEDES, and GUIDES relationships.
                  </p>
                </div>
              </div>
              <div className="shrink-0 font-mono text-xs text-zinc-500">Dual Knowledge Search</div>
            </div>

            <div className="flex flex-col gap-4 rounded-xl border border-zinc-800 bg-zinc-900/30 p-5 md:flex-row md:items-center md:justify-between">
              <div className="flex items-start gap-4">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-zinc-700 bg-zinc-800 text-zinc-200">
                  <IconShieldCheck size={18} />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-zinc-100">3. Compliance Auditor Agent</h3>
                    <span className="rounded bg-zinc-800 px-2 py-0.5 font-mono text-[10px] text-zinc-300">Criterion Evaluator</span>
                  </div>
                  <p className="mt-1 text-xs text-zinc-400">
                    Evaluates enterprise facts against statutory conditions, calculates risk scores, and detects non-compliant operational scenarios.
                  </p>
                </div>
              </div>
              <div className="shrink-0 font-mono text-xs text-zinc-500">Risk Assessment</div>
            </div>

            <div className="flex flex-col gap-4 rounded-xl border border-zinc-800 bg-zinc-900/30 p-5 md:flex-row md:items-center md:justify-between">
              <div className="flex items-start gap-4">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-zinc-700 bg-zinc-800 text-zinc-200">
                  <IconFileText size={18} />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-zinc-100">4. Form Validator Agent</h3>
                    <span className="rounded bg-zinc-800 px-2 py-0.5 font-mono text-[10px] text-zinc-300">Form 11/PLI Dossier</span>
                  </div>
                  <p className="mt-1 text-xs text-zinc-400">
                    Inspects mandatory administrative dossiers, checklists, and statutory application templates required under Vietnamese labor decrees.
                  </p>
                </div>
              </div>
              <div className="shrink-0 font-mono text-xs text-zinc-500">Dossier Validation</div>
            </div>

            <div className="flex flex-col gap-4 rounded-xl border border-zinc-800 bg-zinc-900/30 p-5 md:flex-row md:items-center md:justify-between">
              <div className="flex items-start gap-4">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-emerald-900/50 bg-emerald-950/40 text-emerald-400">
                  <IconSearch size={18} />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-zinc-100">5. Drafting Assistant Agent</h3>
                    <span className="rounded bg-zinc-800 px-2 py-0.5 font-mono text-[10px] text-zinc-300">Synthesis Engine</span>
                  </div>
                  <p className="mt-1 text-xs text-zinc-400">
                    Drafts formal legal opinions, enterprise compliance reports, and explanation documents with verified statutory citations.
                  </p>
                </div>
              </div>
              <div className="shrink-0 font-mono text-xs text-emerald-400">Verified Synthesis</div>
            </div>
          </div>
        </section>

        {/* Section 4: Selective Edge Traversal (Layout Family: Split Comparison Code) */}
        <section id="traversal" className="border-t border-zinc-800/80 py-20">
          <div className="grid grid-cols-1 items-center gap-12 lg:grid-cols-12">
            <div className="lg:col-span-6">
              {/* Eyebrow 2 of 2 */}
              <div className="mb-4 inline-flex items-center gap-2 rounded-md border border-zinc-800 bg-zinc-900 px-2.5 py-1 font-mono text-[11px] uppercase tracking-wider text-zinc-400">
                Selective Edge Traversal
              </div>

              <h2 className="text-3xl font-semibold tracking-tight text-zinc-100 sm:text-4xl">
                Pruning context noise at the graph retrieval layer
              </h2>

              <p className="mt-4 text-sm leading-relaxed text-zinc-400">
                Instead of dumping entire 1-hop subgraphs into prompt payloads, LegalPilot-VN executes targeted Cypher traversals that follow only the specific amendment or guidance edge connected to the queried sub-clause.
              </p>

              <div className="mt-6 rounded-lg border border-zinc-800 bg-zinc-950 p-4 font-mono text-xs">
                <div className="text-zinc-500">// Selective edge query in Neo4j</div>
                <div className="mt-2 text-emerald-400">MATCH (c:Clause &#123;id: $clause_id&#125;)&lt;-[r:AMENDS|GUIDES]-(target:Clause)</div>
                <div className="text-zinc-300">WHERE target.status = &apos;active&apos;</div>
                <div className="text-zinc-300">RETURN target, type(r)</div>
                <div className="text-zinc-300">ORDER BY target.effective_date DESC LIMIT 3;</div>
              </div>

              <div className="mt-6 grid grid-cols-2 gap-4">
                <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
                  <div className="text-xs text-zinc-400">Fixed 1-Hop Dump</div>
                  <div className="mt-1 font-mono text-lg font-bold text-red-400">~3,000 tokens</div>
                  <div className="mt-1 text-[11px] text-zinc-500">60% noise ratio</div>
                </div>
                <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
                  <div className="text-xs text-zinc-400">Selective Traversal</div>
                  <div className="mt-1 font-mono text-lg font-bold text-emerald-400">~450 tokens</div>
                  <div className="mt-1 text-[11px] text-zinc-500">&gt;200% precision lift</div>
                </div>
              </div>
            </div>

            <div className="lg:col-span-6">
              <div className="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/50 shadow-xl">
                <div className="border-b border-zinc-800 bg-zinc-900/80 px-4 py-2.5 font-mono text-xs text-zinc-400">
                  legal-knowledge-graph.cypher
                </div>
                <div className="relative aspect-video w-full bg-zinc-950">
                  <Image
                    src={`${basePath}/images/selective-traversal-graph.jpg`}
                    alt="Legal knowledge graph showing AMENDS and GUIDES edges"
                    fill
                    className="object-cover"
                  />
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Section 5: Hybrid Ingestion Engine (Layout Family: Bento Grid 3-Way Architecture) */}
        <section id="ingestion" className="border-t border-zinc-800/80 py-20">
          <div className="max-w-3xl">
            <h2 className="text-3xl font-semibold tracking-tight text-zinc-100 sm:text-4xl">
              Hybrid parsing pipeline for real-world legal portals
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-zinc-400 sm:text-base">
              Vietnamese legislation is published across varied channels: gazette text, HTML government portals, and non-standard scans. Our ingestion engine adapts dynamically.
            </p>
          </div>

          <div className="mt-12 grid grid-cols-1 gap-6 md:grid-cols-3">
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-zinc-700 bg-zinc-900 text-emerald-400">
                <IconCode size={20} />
              </div>
              <h3 className="mt-4 text-base font-semibold text-zinc-100">HTML DOM Parser</h3>
              <p className="mt-2 text-xs leading-relaxed text-zinc-400">
                Uses BeautifulSoup to parse scraped legal portals (vbpl.vn, thuvienphapluat). Automatically extracts hyperlinked statutory cross-references from anchor tags.
              </p>
              <div className="mt-4 rounded border border-zinc-800 bg-zinc-950 p-2 font-mono text-[11px] text-emerald-400">
                bs4 + Semantic Tag Walk
              </div>
            </div>

            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-zinc-700 bg-zinc-900 text-blue-400">
                <IconLayersLinked size={20} />
              </div>
              <h3 className="mt-4 text-base font-semibold text-zinc-100">Regex Gazette Engine</h3>
              <p className="mt-2 text-xs leading-relaxed text-zinc-400">
                Standardized regex extraction mapping official decrees into Document, Article (Điều), and Clause (Khoản) hierarchy with normalized identifiers.
              </p>
              <div className="mt-4 rounded border border-zinc-800 bg-zinc-950 p-2 font-mono text-[11px] text-blue-400">
                Normalized ID: 152/2020/ND-CP
              </div>
            </div>

            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-zinc-700 bg-zinc-900 text-purple-400">
                <IconSparkles size={20} />
              </div>
              <h3 className="mt-4 text-base font-semibold text-zinc-100">LLM Fallback Parser</h3>
              <p className="mt-2 text-xs leading-relaxed text-zinc-400">
                Invokes Gemini 2.5 Flash when regex or HTML yield 0 articles (scanned/OCR text), outputting strict structured JSON with graceful offline fallback.
              </p>
              <div className="mt-4 rounded border border-zinc-800 bg-zinc-950 p-2 font-mono text-[11px] text-purple-400">
                Gemini 2.5 Flash Fallback
              </div>
            </div>
          </div>

          <div className="mt-6 rounded-xl border border-zinc-800 bg-zinc-950/70 p-4 font-mono text-xs text-zinc-300">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-2 text-zinc-500">
              <span>CLI Batch Ingestion Entrypoint</span>
              <span className="text-emerald-400">v0.1.0</span>
            </div>
            <div className="mt-3 space-y-1">
              <div className="text-zinc-400"># Ingest sample decrees into Neo4j and Qdrant in one command</div>
              <div className="text-emerald-400">$ ./run.sh ingest data/raw</div>
              <div className="text-zinc-500">[+] Parsed 152/2020/ND-CP: 5 articles, 2 cross-references</div>
              <div className="text-zinc-500">[+] Parsed 70/2023/ND-CP: 2 articles, 6 cross-references</div>
              <div className="text-emerald-400">[+] Upserted 17 points into &apos;vietnamese_legal_clauses&apos;</div>
            </div>
          </div>
        </section>

        {/* Section 6: Closed-Loop Claim Auditor (Layout Family: Split Feature with Audit Table) */}
        <section id="auditor" className="border-t border-zinc-800/80 py-20">
          <div className="max-w-3xl">
            <h2 className="text-3xl font-semibold tracking-tight text-zinc-100 sm:text-4xl">
              Self-reflective verification against active statutes
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-zinc-400 sm:text-base">
              The Claim Auditor decomposes provisional answers into atomic claims and cross-checks them one by one. Unsupported assertions or repealed citations trigger iterative correction loops.
            </p>
          </div>

          <div className="mt-10 overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/40">
            <div className="border-b border-zinc-800 bg-zinc-950/60 px-6 py-3 font-mono text-xs text-zinc-400">
              Audit Report: Foreign Specialist Sponsoring Requirements (Decree 152 / Decree 70)
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left font-mono text-xs">
                <thead>
                  <tr className="border-b border-zinc-800 text-zinc-500">
                    <th className="px-6 py-3 font-medium">Claim Proposition</th>
                    <th className="px-6 py-3 font-medium">Cited Statute</th>
                    <th className="px-6 py-3 font-medium">Statute Status</th>
                    <th className="px-6 py-3 font-medium">Auditor Verdict</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/50 text-zinc-300">
                  <tr>
                    <td className="px-6 py-4">Specialist requires university degree and 3 years experience</td>
                    <td className="px-6 py-4">Decree 70/2023 Article 1(1)</td>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center gap-1 text-emerald-400">
                        <IconCheck size={14} /> Active
                      </span>
                    </td>
                    <td className="px-6 py-4 text-emerald-400">Grounded</td>
                  </tr>
                  <tr>
                    <td className="px-6 py-4">Foreign worker must submit original diploma legalized by embassy</td>
                    <td className="px-6 py-4">Decree 152/2020 Article 9(3)</td>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center gap-1 text-emerald-400">
                        <IconCheck size={14} /> Active
                      </span>
                    </td>
                    <td className="px-6 py-4 text-emerald-400">Grounded</td>
                  </tr>
                  <tr>
                    <td className="px-6 py-4">Prior requirement of 5 years management experience still applies</td>
                    <td className="px-6 py-4">Decree 11/2016 Article 3</td>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center gap-1 text-red-400">
                        <IconX size={14} /> Repealed
                      </span>
                    </td>
                    <td className="px-6 py-4 text-red-400">Rejected (Reflect Loop)</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div className="border-t border-zinc-800 bg-zinc-950/80 px-6 py-3 font-mono text-xs text-zinc-400">
              <span className="text-zinc-500">Refinement cycle:</span> 1 of 3 | <span className="text-emerald-400">Final Verification Rate: 100%</span>
            </div>
          </div>
        </section>

        {/* Section 7: Threat Model & Security (Layout Family: Bento Grid) */}
        <section id="threat-model" className="border-t border-zinc-800/80 py-20">
          <div className="max-w-3xl">
            <h2 className="text-3xl font-semibold tracking-tight text-zinc-100 sm:text-4xl">
              Guarded actions and ten-vector adversarial defense
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-zinc-400 sm:text-base">
              Enterprise compliance requires defense against indirect prompt injection, data poisoning, and unauthorized automated filings.
            </p>
          </div>

          <div className="mt-12 grid grid-cols-1 gap-6 md:grid-cols-3">
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6 md:col-span-2">
              <div className="flex items-center gap-2 text-xs font-semibold text-emerald-400">
                <IconLock size={16} />
                <span>Vector 8: Human Confirmation Token Gate</span>
              </div>
              <h3 className="mt-2 text-base font-semibold text-zinc-100">
                Irreversible actions demand explicit officer authorization
              </h3>
              <p className="mt-2 text-xs leading-relaxed text-zinc-400">
                Any tool invocation that exports compliance dossiers or submits filings generates a short-lived token (CONFIRM-XXXX) persisted in SQLite. The action halts execution until verified by an authorized officer.
              </p>
              <div className="mt-4 flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-950 p-3 font-mono text-xs">
                <span className="text-zinc-500">Token Status:</span>
                <span className="rounded bg-emerald-950 px-2 py-0.5 text-emerald-400">CONFIRM-A4F9</span>
                <span className="text-zinc-400">Action: submit_portal_filing</span>
              </div>
            </div>

            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
              <div className="text-xs font-semibold text-zinc-300">Vector 1: Zero-Width Text</div>
              <h3 className="mt-2 text-sm font-semibold text-zinc-100">Sanitizing Hidden Font Layers</h3>
              <p className="mt-2 text-xs leading-relaxed text-zinc-400">
                Strips zero-width characters and prompt injection delimiters from uploaded documents before model ingestion.
              </p>
              <div className="mt-4 font-mono text-[11px] text-zinc-500">
                Regex: [\u200B-\u200D\uFEFF]
              </div>
            </div>

            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
              <div className="text-xs font-semibold text-zinc-300">Vector 5: SQL Injection</div>
              <h3 className="mt-2 text-sm font-semibold text-zinc-100">100% Parameterized SQLite</h3>
              <p className="mt-2 text-xs leading-relaxed text-zinc-400">
                All database access across enterprise profile, audit history, and statute cache strictly uses parameterized queries.
              </p>
              <div className="mt-4 font-mono text-[11px] text-zinc-500">
                Status: Syntax Isolation Active
              </div>
            </div>

            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6 md:col-span-2">
              <div className="text-xs font-semibold text-zinc-300">Vectors 9 & 10: DoS and Path Traversal</div>
              <h3 className="mt-2 text-base font-semibold text-zinc-100">
                Strict Traversal Caps and Directory Confinement
              </h3>
              <p className="mt-2 text-xs leading-relaxed text-zinc-400">
                Search depth is strictly capped at 2 hops and 5 documents max to prevent denial of service. File export operations strip parent-directory sequences and are confined exclusively to workspace folders.
              </p>
              <div className="mt-4 flex flex-wrap gap-4 font-mono text-xs">
                <span className="text-zinc-400">Max Depth: 2 Hops</span>
                <span className="text-zinc-400">Max Docs: 5</span>
                <span className="text-zinc-400">Timeout: 12s</span>
              </div>
            </div>
          </div>
        </section>

        {/* Section 8: Architecture Decision Records (Layout Family: 4-Card Grid) */}
        <section id="adrs" className="border-t border-zinc-800/80 py-20">
          <div className="max-w-3xl">
            <h2 className="text-3xl font-semibold tracking-tight text-zinc-100 sm:text-4xl">
              Documented architectural decisions and engineering specifications
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-zinc-400 sm:text-base">
              Explore the complete technical rationale, trade-off evaluations, and system schemas in the newly organized documentation library.
            </p>
          </div>

          <div className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-2">
            <a
              href="https://github.com/DangLamTung/CO5151/blob/main/docs/adr/0001-multi-agent-adk.md"
              target="_blank"
              rel="noreferrer"
              className="group rounded-xl border border-zinc-800 bg-zinc-900/40 p-6 transition hover:border-zinc-700 hover:bg-zinc-900/70"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs text-emerald-400">ADR-0001</span>
                <span className="rounded bg-zinc-800 px-2 py-0.5 font-mono text-[10px] text-zinc-400">Accepted</span>
              </div>
              <h3 className="mt-3 text-base font-semibold text-zinc-100 group-hover:text-emerald-400">
                Multi-Agent Orchestration via Google ADK
              </h3>
              <p className="mt-2 text-xs leading-relaxed text-zinc-400">
                Rationale for decomposing legal workflows into Lead Counsel, Research, Audit, Form, and Drafting specialists.
              </p>
            </a>

            <a
              href="https://github.com/DangLamTung/CO5151/blob/main/docs/adr/0002-dual-storage-graph-vector.md"
              target="_blank"
              rel="noreferrer"
              className="group rounded-xl border border-zinc-800 bg-zinc-900/40 p-6 transition hover:border-zinc-700 hover:bg-zinc-900/70"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs text-emerald-400">ADR-0002</span>
                <span className="rounded bg-zinc-800 px-2 py-0.5 font-mono text-[10px] text-zinc-400">Accepted</span>
              </div>
              <h3 className="mt-3 text-base font-semibold text-zinc-100 group-hover:text-emerald-400">
                Dual Storage: Neo4j Graph + Qdrant Vector
              </h3>
              <p className="mt-2 text-xs leading-relaxed text-zinc-400">
                Why vector similarity alone fails in legal RAG and how graph hierarchy eliminates citation hallucination.
              </p>
            </a>

            <a
              href="https://github.com/DangLamTung/CO5151/blob/main/docs/adr/0003-selective-temporal-traversal.md"
              target="_blank"
              rel="noreferrer"
              className="group rounded-xl border border-zinc-800 bg-zinc-900/40 p-6 transition hover:border-zinc-700 hover:bg-zinc-900/70"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs text-emerald-400">ADR-0003</span>
                <span className="rounded bg-zinc-800 px-2 py-0.5 font-mono text-[10px] text-zinc-400">Accepted</span>
              </div>
              <h3 className="mt-3 text-base font-semibold text-zinc-100 group-hover:text-emerald-400">
                Selective Temporal Traversal
              </h3>
              <p className="mt-2 text-xs leading-relaxed text-zinc-400">
                Dynamic resolution of amendment and repeal edges across changing decree versions (Decree 152 vs Decree 70).
              </p>
            </a>

            <a
              href="https://github.com/DangLamTung/CO5151/blob/main/docs/adr/0004-sqlite-memory-and-token-gate.md"
              target="_blank"
              rel="noreferrer"
              className="group rounded-xl border border-zinc-800 bg-zinc-900/40 p-6 transition hover:border-zinc-700 hover:bg-zinc-900/70"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs text-emerald-400">ADR-0004</span>
                <span className="rounded bg-zinc-800 px-2 py-0.5 font-mono text-[10px] text-zinc-400">Accepted</span>
              </div>
              <h3 className="mt-3 text-base font-semibold text-zinc-100 group-hover:text-emerald-400">
                SQLite Memory & Tiered Token Gating
              </h3>
              <p className="mt-2 text-xs leading-relaxed text-zinc-400">
                Zero-maintenance embedded persistence for compliance audit trails and hard token budgeting ceilings.
              </p>
            </a>
          </div>
        </section>

        {/* Section 9: Quickstart Action Box (Layout Family: Full-Width Action Box) */}
        <section id="demo" className="border-t border-zinc-800/80 py-20">
          <div className="rounded-2xl border border-zinc-800 bg-gradient-to-b from-zinc-900/80 to-zinc-950 p-8 sm:p-12">
            <div className="max-w-2xl">
              <h2 className="text-3xl font-semibold tracking-tight text-zinc-100 sm:text-4xl">
                Ready to run locally in under five minutes
              </h2>
              <p className="mt-3 text-sm leading-relaxed text-zinc-400">
                Initialize the environment, ingest sample decrees, and launch the multi-agent Streamlit assistant with single-command workflows.
              </p>
            </div>

            <div className="mt-8 rounded-xl border border-zinc-800 bg-zinc-950 p-4 font-mono text-xs text-zinc-300">
              <div className="text-zinc-500">// 1. Foundation setup (Docker + SQLite + .env)</div>
              <div className="text-emerald-400">$ ./run.sh setup</div>
              <div className="mt-2 text-zinc-500">// 2. Ingest legal documents into Neo4j and Qdrant</div>
              <div className="text-emerald-400">$ ./run.sh ingest data/raw</div>
              <div className="mt-2 text-zinc-500">// 3. Start the Web UI</div>
              <div className="text-emerald-400">$ ./run.sh ui</div>
            </div>

            <div className="mt-8 flex flex-wrap items-center gap-4">
              <a
                href="https://github.com/DangLamTung/CO5151"
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-11 items-center gap-2 rounded-md bg-emerald-500 px-6 text-sm font-semibold text-black transition hover:bg-emerald-400 active:scale-[0.98]"
              >
                Launch on GitHub
                <IconArrowRight size={16} />
              </a>
              <a
                href="https://github.com/DangLamTung/CO5151/tree/main/docs"
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-11 items-center rounded-md border border-zinc-800 bg-zinc-900 px-6 text-sm font-medium text-zinc-300 transition hover:border-zinc-700 hover:text-white active:scale-[0.98]"
              >
                Read Documentation
              </a>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-zinc-800/80 py-8 text-center font-mono text-xs text-zinc-500">
        <div className="mx-auto max-w-7xl px-6">
          CO5151 Advanced Agentic AI | Advisor: Dr. Le Xuan Bach | Dang Lam Tung, Nguyen Trung Phong, Vu Viet Hung
        </div>
      </footer>
    </div>
  );
}
