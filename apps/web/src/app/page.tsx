"use client";

import { FormEvent, useEffect, useState } from "react";
import styles from "./page.module.css";

type EvalCase = { case_id: string; question: string; context_anchor_keys?: string[]; acceptable_anchor_keys: string[]; preferred_anchor_keys?: string[]; expected_abstain?: boolean; human_review_criteria?: string[] };
type Suite = { id: "retrieval" | "generation" | "answer"; label: string; path: string; case_count: number; cases: EvalCase[] };
type Fixture = { id: Suite["id"]; path: string; content: string; sha256: string; cases: EvalCase[] };
type Artifact = { name: string; kind?: "run" | "baseline"; size_bytes: number; modified_at: number; format: string; suite_id?: string; strategy?: string; provider?: string | null; finished_at?: string; label?: string | null; headline_metric?: string; headline_value?: number | null; case_count?: number; passed?: number; fixture_is_current?: boolean; promoted_from?: string | null };
type Evidence = { rank?: number; chunk_id: string; anchor_key: string; anchor_title: string; source_title: string; source_link: string; score?: number | null; excerpt: string };
type DebugResult = { answer: { display_text: string; outcome: string; claims: Array<{ text: string; citations: Array<{ anchor_key: string; source_title: string; source_link: string }> }> }; retrieved_chunks: Evidence[]; diagnostics: { validation_error: string | null; rejected_draft: unknown | null } };
type EvalOutcome = { artifact_name: string; summary: Record<string, number | null>; cases: Array<{ case_id: string; question: string; topic?: string; edge_case?: string; passed: boolean; acceptable_anchor_keys: string[]; preferred_anchor_keys?: string[]; acceptable_rank?: number | null; preferred_rank?: number | null; expected_abstain?: boolean; actual_outcome?: string; cited_acceptable_anchor_keys?: string[]; human_review_criteria?: string[]; answer?: { display_text: string }; validation_error?: string | null; retrieved_evidence: Evidence[] }> };

type RunArtifact = EvalOutcome & { run_id: string; suite_id: Suite["id"]; strategy: string; provider: string | null; embedding_model: string | null; answer_model?: string | null; fixture_sha256: string; finished_at: string; baseline?: { label: string; promoted_at: string; source_artifact: string } };
type RunJob = { job_id: string; status: "running" | "succeeded" | "failed"; completed: number; total: number | null; result: EvalOutcome | null; error: string | null };
type Comparison = { baseline: string; candidate: string; strategies: string[]; warnings: string[]; metrics: Record<string, { baseline: number; candidate: number; delta: number }>; added_case_ids: string[]; removed_case_ids: string[]; changes: Array<{ case_id: string; question: string; change: "regressed" | "improved" | "rank_changed"; baseline_rank?: number | null; candidate_rank?: number | null; baseline_outcome?: string | null; candidate_outcome?: string | null }> };

// Quick reads fail fast; long work (suite runs) goes through background jobs that are polled.
async function api<T>(path: string, init?: RequestInit, timeoutMs = 10_000): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`/api/taxrag${path}`, { ...init, signal: controller.signal, headers: { "Content-Type": "application/json", ...init?.headers } });
    const body = (await response.json()) as T & { detail?: string };
    if (!response.ok) throw new Error(body.detail ?? `Request failed (${response.status})`);
    return body;
  } catch (error) {
    if (controller.signal.aborted) throw new Error(`Request to ${path} timed out after ${Math.round(timeoutMs / 1000)} seconds.`);
    if (error instanceof TypeError) throw new Error("Cannot reach TaxRAG API. Check the API and Next.js development servers.");
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

export default function Home() {
  const [tab, setTab] = useState<"suites" | "archive" | "question">("suites");
  const [suites, setSuites] = useState<Suite[]>([]);
  const [selectedSuite, setSelectedSuite] = useState<Suite["id"]>("retrieval");
  const [fixture, setFixture] = useState<Fixture | null>(null);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [artifactContent, setArtifactContent] = useState("");
  const [archiveRun, setArchiveRun] = useState<RunArtifact | null>(null);
  const [archiveName, setArchiveName] = useState("");
  const [baselineLabel, setBaselineLabel] = useState("v0");
  const [compareWith, setCompareWith] = useState("");
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [suiteOutcome, setSuiteOutcome] = useState<EvalOutcome | null>(null);
  const [suiteStrategy, setSuiteStrategy] = useState("lexical");
  const [suiteProvider, setSuiteProvider] = useState("fake");
  const [confirmSuitePaid, setConfirmSuitePaid] = useState(false);
  const [question, setQuestion] = useState("Recebi 30 mil em rendimentos tributáveis em 2025. Devo declarar?");
  const [strategy, setStrategy] = useState("lexical");
  const [provider, setProvider] = useState("fake");
  const [confirmPaid, setConfirmPaid] = useState(false);
  const [debugResult, setDebugResult] = useState<DebugResult | null>(null);
  const [selectedAnchors, setSelectedAnchors] = useState<string[]>([]);
  const [preferredAnchor, setPreferredAnchor] = useState("");
  const [expectedAbstain, setExpectedAbstain] = useState(false);
  const [reviewCriteria, setReviewCriteria] = useState("");
  const [notice, setNotice] = useState("Loading local evaluation workspace...");
  const [workspaceLoading, setWorkspaceLoading] = useState(true);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [busy, setBusy] = useState(false);

  async function refreshArtifacts() {
    const result = await api<{ artifacts: Artifact[] }>("/api/evals/artifacts");
    return result.artifacts;
  }
  useEffect(() => {
    void Promise.all([api<{ suites: Suite[] }>("/api/evals/suites"), refreshArtifacts()])
      .then(([result, savedArtifacts]) => { setSuites(result.suites); setArtifacts(savedArtifacts); setNotice("Local workspace ready. Suite fixtures are Git-tracked."); })
      .catch((error: Error) => setNotice(`Could not load the local workspace: ${error.message}`))
      .finally(() => setWorkspaceLoading(false));
  }, [loadAttempt]);
  useEffect(() => {
    void api<Fixture>(`/api/evals/suites/${selectedSuite}/fixture`).then(setFixture).catch((error: Error) => setNotice(error.message));
  }, [selectedSuite]);

  async function saveFixture(content = fixture?.content) {
    if (!fixture || content === undefined) return;
    const saved = await api<Fixture>(`/api/evals/suites/${fixture.id}/fixture`, { method: "PUT", body: JSON.stringify({ content }) });
    setFixture(saved);
    setNotice(`Validated and saved ${saved.path}. Review the Git diff before committing.`);
  }
  async function runSelectedSuite() {
    setBusy(true); setSuiteOutcome(null);
    try {
      let job = await api<RunJob>(`/api/evals/suites/${selectedSuite}/jobs`, { method: "POST", body: JSON.stringify({ strategy: suiteStrategy, provider: selectedSuite === "retrieval" ? "fake" : suiteProvider, confirm_paid_request: confirmSuitePaid }) });
      // Poll with short requests; a long run never depends on one HTTP request staying open.
      while (job.status === "running") {
        setNotice(`Running ${selectedSuite} suite (${suiteStrategy})… ${job.completed}/${job.total ?? "?"} cases. You can keep this tab open; the run continues on the API.`);
        await new Promise((resolve) => setTimeout(resolve, 1500));
        job = await api<RunJob>(`/api/evals/jobs/${job.job_id}`);
      }
      if (job.status === "failed" || !job.result) throw new Error(job.error ?? "Suite run failed.");
      setSuiteOutcome(job.result); setArtifacts(await refreshArtifacts()); setNotice(`Run saved to var/eval-runs/${job.result.artifact_name}. Open it in Run archive to save it as a baseline or compare it.`);
    } catch (error) { setNotice(error instanceof Error ? error.message : "Suite run failed."); }
    finally { setBusy(false); }
  }
  async function openArtifact(name: string) {
    try {
      const artifact = await api<{ name: string; content: string }>(`/api/evals/artifacts/${encodeURIComponent(name)}`, undefined, 30_000);
      setArtifactContent(artifact.content); setArchiveName(name); setComparison(null); setCompareWith("");
      try { const parsed = JSON.parse(artifact.content) as RunArtifact; setArchiveRun(parsed.summary && parsed.cases ? { ...parsed, artifact_name: name } : null); } catch { setArchiveRun(null); }
    }
    catch (error) { setNotice(error instanceof Error ? error.message : "Artifact could not be opened."); }
  }
  async function promoteBaseline() {
    if (!archiveName) return;
    try {
      const promoted = await api<{ name: string; path: string }>("/api/evals/baselines", { method: "POST", body: JSON.stringify({ artifact_name: archiveName, label: baselineLabel.trim() }) });
      setArtifacts(await refreshArtifacts()); setNotice(`Baseline saved to ${promoted.path}. Commit it so it survives var/ cleanup and can be shared.`);
    } catch (error) { setNotice(error instanceof Error ? error.message : "Baseline could not be saved."); }
  }
  async function compareToBaseline(baseline: string) {
    setCompareWith(baseline); setComparison(null);
    if (!baseline || !archiveName) return;
    try { setComparison(await api<Comparison>(`/api/evals/compare?baseline=${encodeURIComponent(baseline)}&candidate=${encodeURIComponent(archiveName)}`, undefined, 30_000)); }
    catch (error) { setNotice(error instanceof Error ? error.message : "Comparison failed."); }
  }
  async function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setDebugResult(null); setSelectedAnchors([]); setPreferredAnchor("");
    try {
      const result = await api<DebugResult>("/api/evals/debug-answer", { method: "POST", body: JSON.stringify({ question, strategy, provider, confirm_paid_request: confirmPaid }) });
      setDebugResult(result); setNotice("Diagnostic complete. Select supporting anchors below to add it to a suite.");
    } catch (error) { setNotice(error instanceof Error ? error.message : "Question could not be evaluated."); }
    finally { setBusy(false); }
  }
  async function addDiagnosticCase() {
    if (!fixture || !debugResult) return;
    const answerSuite = selectedSuite !== "retrieval";
    const anchors = expectedAbstain && answerSuite ? [] : selectedAnchors;
    if (selectedSuite === "retrieval" && anchors.length === 0) { setNotice("Select at least one acceptable anchor before saving this retrieval case."); return; }
    if (answerSuite && !expectedAbstain && anchors.length === 0) { setNotice("Select an acceptable anchor, or mark expected abstention."); return; }
    const prefix = { retrieval: "lex", generation: "gen", answer: "answer" }[selectedSuite];
    const nextNumber = Math.max(0, ...fixture.cases.map((item) => Number(item.case_id.match(/(\d+)$/)?.[1] ?? 0))) + 1;
    const record: Record<string, unknown> = { id: `${prefix}-${String(nextNumber).padStart(3, "0")}`, question: question.trim(), acceptable_anchor_keys: anchors };
    if (selectedSuite === "retrieval") record.preferred_anchor_keys = preferredAnchor && anchors.includes(preferredAnchor) ? [preferredAnchor] : [];
    else {
      // A generation case freezes the diagnostic's retrieved chunks as its fixed evidence.
      if (selectedSuite === "generation") record.context_anchor_keys = debugResult.retrieved_chunks.map((chunk) => chunk.anchor_key);
      const criteria = reviewCriteria.split("\n").map((item) => item.trim()).filter(Boolean);
      if (criteria.length === 0) { setNotice("Add at least one human review criterion for an answer case."); return; }
      record.expected_abstain = expectedAbstain; record.human_review_criteria = criteria;
    }
    const content = `${fixture.content.trimEnd()}\n${JSON.stringify(record)}\n`;
    setBusy(true);
    try { await saveFixture(content); setNotice(`Added ${record.id} to ${fixture.path}; fixture validation passed.`); setSelectedAnchors([]); setPreferredAnchor(""); }
    catch (error) { setNotice(error instanceof Error ? error.message : "Diagnostic case could not be saved."); }
    finally { setBusy(false); }
  }
  function changeSuite(id: Suite["id"]) {
    setSelectedSuite(id);
    setSuiteOutcome(null);
  }
  function retryWorkspaceLoad() {
    setWorkspaceLoading(true);
    setNotice("Retrying local workspace connection...");
    setLoadAttempt((attempt) => attempt + 1);
  }

  const suiteNeedsPaidRequest = (selectedSuite !== "generation" && PAID_STRATEGIES.has(suiteStrategy)) || (selectedSuite !== "retrieval" && suiteProvider === "openai");
  const questionNeedsPaidRequest = PAID_STRATEGIES.has(strategy) || provider === "openai";
  const activeSuite = suites.find((item) => item.id === selectedSuite);

  return <main className={styles.main}>
    <section className={styles.hero}><p className={styles.eyebrow}>TaxRAG / Local developer tool</p><h1>Eval Workshop</h1><p>Run suites, inspect failures, and turn diagnostic queries into reviewable test cases.</p></section>
    <nav className={styles.tabs} aria-label="Eval Manager sections"><button className={tab === "suites" ? styles.active : ""} onClick={() => setTab("suites")}>Suites & cases</button><button className={tab === "archive" ? styles.active : ""} onClick={() => setTab("archive")}>Run archive</button><button className={tab === "question" ? styles.active : ""} onClick={() => setTab("question")}>Question lab</button></nav>
    <div className={styles.notice} role="status" aria-live="polite"><span>{notice}</span>{!workspaceLoading && notice.startsWith("Could not load the local workspace:") && <button className={styles.retry} onClick={retryWorkspaceLoad}>Retry connection</button>}</div>
    {tab === "suites" && <section className={styles.workspace}>
      <aside className={styles.sidebar}><h2>Versioned suites</h2>{suites.map((suite) => <button key={suite.id} className={selectedSuite === suite.id ? styles.suiteSelected : styles.suite} onClick={() => changeSuite(suite.id)}><strong>{suite.label}</strong><span>{suite.case_count} cases</span><small>{suite.path}</small></button>)}</aside>
      <div className={styles.editor}>
        <div className={styles.sectionTitle}><div><p className={styles.eyebrow}>Run and review</p><h2>{activeSuite?.label ?? "Evaluation suite"}</h2><small>{fixture?.path}</small></div><button className={styles.primary} disabled={busy || !fixture || (suiteNeedsPaidRequest && !confirmSuitePaid)} onClick={runSelectedSuite}>{busy ? "Running suite…" : "Run suite"}</button></div>
        <div className={styles.runControls}>{selectedSuite !== "generation" ? <label>Retrieval strategy<select value={suiteStrategy} onChange={(event) => setSuiteStrategy(event.target.value)}><StrategyOptions /></select></label> : <p>Evidence is fixed per case; retrieval is not used.</p>}{selectedSuite !== "retrieval" && <label>Answer provider<select value={suiteProvider} onChange={(event) => setSuiteProvider(event.target.value)}><option value="fake">Deterministic fake (no API)</option><option value="openai">OpenAI (billable)</option></select></label>}</div>
        {suiteNeedsPaidRequest && <label className={styles.consent}><input type="checkbox" checked={confirmSuitePaid} onChange={(event) => setConfirmSuitePaid(event.target.checked)} /> I confirm this may send official chunks to OpenAI and incur API cost.</label>}
        <p className={styles.warning}>Local only: saving fixtures changes Git-tracked JSONL. Runs are saved under <code>var/eval-runs/</code>.</p>
        {suiteOutcome && <SuiteResult result={suiteOutcome} onOpenArtifact={() => { setTab("archive"); void openArtifact(suiteOutcome.artifact_name); }} />}
        <details className={styles.fixtureDetails}><summary>Edit raw fixture JSONL</summary><div className={styles.sectionTitle}><span>Validate before saving</span><button className={styles.secondary} disabled={busy || !fixture} onClick={() => void saveFixture()}>Validate & save fixture</button></div><textarea aria-label="JSONL fixture" value={fixture?.content ?? ""} onChange={(event) => fixture && setFixture({ ...fixture, content: event.target.value })} /></details>
        <h3>Cases ({fixture?.cases.length ?? 0})</h3><div className={styles.caseGrid}>{fixture?.cases.map((item) => <article key={item.case_id}><code>{item.case_id}</code><p>{item.question}</p>{item.context_anchor_keys?.length ? <small>Context: {item.context_anchor_keys.join(" · ")}</small> : null}<small>{item.acceptable_anchor_keys.length ? `${item.context_anchor_keys?.length ? "Must cite one of" : "Acceptable"}: ${item.acceptable_anchor_keys.join(" · ")}` : "No support anchors (expected abstention)"}</small></article>)}</div>
      </div>
    </section>}
    {tab === "archive" && <section className={styles.archive}><div><p className={styles.eyebrow}>Local history and Git-tracked baselines</p><h2>Saved runs</h2><p>Runs live in <code>var/eval-runs/</code> (local, not committed). Promote a run to a baseline to keep it in <code>docs/evals/baselines/</code> and compare later runs against it. Times are shown in your local time zone; file names use UTC.</p></div>
      <ArchiveTable artifacts={artifacts} selected={archiveName} onOpen={(name) => void openArtifact(name)} />
      {archiveRun && <section className={styles.runMeta}><div><p className={styles.eyebrow}>{archiveRun.baseline ? `Baseline “${archiveRun.baseline.label}”` : "Run"} · {archiveRun.suite_id} suite</p><h3>{archiveRun.strategy}{archiveRun.provider ? ` · ${archiveRun.provider}` : ""}{archiveRun.embedding_model ? ` · ${archiveRun.embedding_model}` : ""}{archiveRun.answer_model ? ` · ${archiveRun.answer_model}` : ""}</h3><small>Finished {new Date(archiveRun.finished_at).toLocaleString(undefined, { timeZoneName: "short" })} · fixture {archiveRun.fixture_sha256.slice(0, 12)}</small></div>
        <div className={styles.runControls}>{!archiveRun.baseline && <label>Save as baseline (label)<span className={styles.inline}><input value={baselineLabel} onChange={(event) => setBaselineLabel(event.target.value)} placeholder="v0" /><button className={styles.secondary} onClick={() => void promoteBaseline()}>Save baseline</button></span></label>}<label>Compare with baseline<select value={compareWith} onChange={(event) => void compareToBaseline(event.target.value)}><option value="">Select a baseline…</option>{artifacts.filter((item) => item.kind === "baseline" && item.name !== archiveName && item.name.includes(`_${archiveRun.suite_id}_`)).map((item) => <option key={item.name} value={item.name}>{item.name}</option>)}</select></label></div>
        {comparison && <ComparisonPanel comparison={comparison} />}
      </section>}
      {archiveRun && <SuiteResult result={archiveRun} onOpenArtifact={() => undefined} showOpen={false} />}
      <details className={styles.fixtureDetails}><summary>Raw JSON</summary><pre className={styles.artifactContent}>{artifactContent || "Select a saved run to inspect its complete JSON artifact."}</pre></details></section>}
    {tab === "question" && <section className={styles.questionLab}><div><p className={styles.eyebrow}>One explicit run</p><h2>Question lab</h2><p>Run a diagnostic, inspect evidence, then add the query to a suite without retyping it.</p></div><form onSubmit={submitQuestion} className={styles.questionForm}><label>Question<textarea value={question} onChange={(event) => setQuestion(event.target.value)} /></label><div className={styles.runControls}><label>Retrieval strategy<select value={strategy} onChange={(event) => setStrategy(event.target.value)}><StrategyOptions /></select></label><label>Answer provider<select value={provider} onChange={(event) => setProvider(event.target.value)}><option value="fake">Deterministic fake (no API call)</option><option value="openai">OpenAI (billable)</option></select></label></div>{questionNeedsPaidRequest && <label className={styles.consent}><input type="checkbox" checked={confirmPaid} onChange={(event) => setConfirmPaid(event.target.checked)} /> I understand the question and chunks may be sent to OpenAI and incur cost.</label>}<button className={styles.primary} disabled={busy || (questionNeedsPaidRequest && !confirmPaid)}>{busy ? "Running…" : "Run diagnostic"}</button></form>
      {debugResult && <><DebugPanel result={debugResult} /><section className={styles.addCase}><p className={styles.eyebrow}>Add this query to a suite</p><h3>Turn diagnostic into a test case</h3><label>Target suite<select value={selectedSuite} onChange={(event) => changeSuite(event.target.value as Suite["id"])}><option value="retrieval">Retrieval (chunks only)</option><option value="generation">Answer generation (fixed evidence)</option><option value="answer">End-to-end answers</option></select></label>{selectedSuite !== "retrieval" && <label className={styles.consent}><input type="checkbox" checked={expectedAbstain} onChange={(event) => setExpectedAbstain(event.target.checked)} /> Expect the answer provider to abstain</label>}
        {!(selectedSuite !== "retrieval" && expectedAbstain) && <div className={styles.anchorPicker}><strong>Select acceptable support chunks</strong>{debugResult.retrieved_chunks.map((chunk) => <label key={chunk.chunk_id}><input type="checkbox" checked={selectedAnchors.includes(chunk.anchor_key)} onChange={(event) => setSelectedAnchors((current) => event.target.checked ? [...new Set([...current, chunk.anchor_key])] : current.filter((key) => key !== chunk.anchor_key))} /><span>{chunk.anchor_key} · {chunk.anchor_title}</span></label>)}{debugResult.retrieved_chunks.length === 0 && <p>No chunks returned. Choose expected abstention for an answer case.</p>}</div>}
        {selectedSuite === "retrieval" && <label>Preferred anchor (optional)<select value={preferredAnchor} onChange={(event) => setPreferredAnchor(event.target.value)}><option value="">No preferred source</option>{selectedAnchors.map((anchor) => <option key={anchor} value={anchor}>{anchor}</option>)}</select></label>}{selectedSuite !== "retrieval" && <label>Human review criteria (one per line)<textarea value={reviewCriteria} onChange={(event) => setReviewCriteria(event.target.value)} placeholder="Directly answers the question.&#10;Uses an acceptable official citation." /></label>}<button className={styles.secondary} disabled={busy || !fixture} onClick={() => void addDiagnosticCase()}>Validate and add to {selectedSuite} suite</button></section></>}
    </section>}
  </main>;
}

// "Semantic" is the production pipeline (TAXRAG_ANSWER_STRATEGY); others are diagnostics.
// Strategies that call OpenAI (question embeddings and/or the reranker).
const PAID_STRATEGIES = new Set(["semantic", "hybrid_rrf", "hybrid_rerank"]);

function StrategyOptions() { return <><option value="semantic">Semantic (production)</option><option value="hybrid_rerank">Hybrid + LLM rerank (candidate)</option><option value="lexical">Lexical (diagnostic)</option><option value="lexical_authority">Lexical + authority (diagnostic)</option><option value="hybrid_rrf">Hybrid RRF (diagnostic)</option></>; }

function EvidenceList({ items }: { items: Evidence[] }) {
  return <div className={styles.evidence}>{items.map((item, index) => <details key={`${item.chunk_id}-${index}`}><summary>{item.rank ? `#${item.rank} ` : ""}{item.anchor_key}{typeof item.score === "number" && <span>score {item.score.toFixed(4)}</span>}</summary><p><a href={item.source_link} target="_blank" rel="noreferrer">Open {item.source_title} · {item.anchor_title}</a></p><p>{item.excerpt}</p></details>)}</div>;
}

function SuiteResult({ result, onOpenArtifact, showOpen = true }: { result: EvalOutcome; onOpenArtifact: () => void; showOpen?: boolean }) {
  const [failuresOnly, setFailuresOnly] = useState(false);
  const metrics = Object.entries(result.summary).filter(([, value]) => typeof value === "number");
  const cases = failuresOnly ? result.cases.filter((item) => !item.passed) : result.cases;
  return <section className={styles.suiteResults}><div className={styles.sectionTitle}><div><p className={styles.eyebrow}>Saved run · {result.artifact_name}</p><h3>Run summary</h3></div>{showOpen && <button className={styles.secondary} onClick={onOpenArtifact}>Open in run archive</button>}</div><div className={styles.metricGrid}>{metrics.map(([name, value]) => <div key={name}><small>{name.replaceAll("_", " ")}</small><strong>{(name.includes("rate") || name.includes("recall")) && value !== null ? `${(value * 100).toFixed(0)}%` : value}</strong></div>)}</div><div className={styles.sectionTitle}><h3>Case results ({cases.length})</h3><label className={styles.consent}><input type="checkbox" checked={failuresOnly} onChange={(event) => setFailuresOnly(event.target.checked)} /> Show only cases needing review</label></div><div className={styles.resultCases}>{cases.map((item) => <article key={item.case_id} className={item.passed ? styles.resultPass : styles.resultFail}><div><strong>{item.case_id}{item.topic && <span className={styles.tag}>{item.topic}</span>}{item.edge_case && <span className={styles.edgeTag}>edge: {item.edge_case}</span>}</strong><span>{item.passed ? "Pass" : "Needs review"}</span></div><p>{item.question}</p>{item.acceptable_rank !== undefined && <small>Acceptable rank: {item.acceptable_rank ?? "outside top 3"}{item.preferred_anchor_keys?.length ? ` · preferred rank: ${item.preferred_rank ?? "outside top 3"}` : ""} · expected: {item.acceptable_anchor_keys.join(", ")}</small>}{item.actual_outcome && <small>Expected: {item.expected_abstain ? "abstain" : "answer"} · outcome: {item.actual_outcome} · acceptable citation: {item.cited_acceptable_anchor_keys?.join(", ") || "none"}</small>}{item.answer?.display_text && <p>{item.answer.display_text}</p>}{item.validation_error && <small className={styles.blocked}>Blocked before display: {item.validation_error}</small>}{item.human_review_criteria?.length ? <ul>{item.human_review_criteria.map((criterion) => <li key={criterion}>{criterion}</li>)}</ul> : null}{item.retrieved_evidence?.length ? <EvidenceList items={item.retrieved_evidence} /> : null}</article>)}</div></section>;
}

const SUITE_NAMES: Record<string, string> = { retrieval: "Retrieval", generation: "Generation", answer: "End-to-end" };

function formatWhen(artifact: Artifact) {
  const when = artifact.finished_at ? new Date(artifact.finished_at) : new Date(artifact.modified_at * 1000);
  // dateStyle/timeStyle cannot be combined with timeZoneName, so list the fields explicitly.
  return when.toLocaleString(undefined, { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", timeZoneName: "short" });
}

function ArchiveTable({ artifacts, selected, onOpen }: { artifacts: Artifact[]; selected: string; onOpen: (name: string) => void }) {
  const [kind, setKind] = useState("all");
  const [suite, setSuite] = useState("all");
  const [strategy, setStrategy] = useState("all");
  const [label, setLabel] = useState("all");
  const [currentOnly, setCurrentOnly] = useState(false);
  const [hidePromoted, setHidePromoted] = useState(true);
  const promoted = new Set(artifacts.map((item) => item.promoted_from).filter(Boolean));
  const values = (key: keyof Artifact) => [...new Set(artifacts.map((item) => item[key]).filter((value): value is string => typeof value === "string"))].sort();
  const rows = artifacts.filter((item) => (kind === "all" || item.kind === kind) && (suite === "all" || item.suite_id === suite) && (strategy === "all" || item.strategy === strategy) && (label === "all" || item.label === label) && (!currentOnly || item.fixture_is_current) && !(hidePromoted && item.kind === "run" && promoted.has(item.name)));
  const select = (name: string, value: string, set: (value: string) => void, options: string[], names: Record<string, string> = {}) => <label>{name}<select value={value} onChange={(event) => set(event.target.value)}><option value="all">All</option>{options.map((option) => <option key={option} value={option}>{names[option] ?? option}</option>)}</select></label>;
  return <div className={styles.archiveTable}>
    <div className={styles.runControls}>{select("Kind", kind, setKind, ["baseline", "run"], { baseline: "Baselines", run: "Runs" })}{select("Suite", suite, setSuite, values("suite_id"), SUITE_NAMES)}{select("Strategy", strategy, setStrategy, values("strategy"))}{select("Baseline label", label, setLabel, values("label"))}<label className={styles.consent}><input type="checkbox" checked={currentOnly} onChange={(event) => setCurrentOnly(event.target.checked)} /> Current fixture only</label><label className={styles.consent}><input type="checkbox" checked={hidePromoted} onChange={(event) => setHidePromoted(event.target.checked)} /> Hide runs already saved as baselines</label></div>
    <table><thead><tr><th>Kind</th><th>Suite</th><th>Strategy · provider</th><th>Finished</th><th>Result</th><th>Fixture</th></tr></thead><tbody>
      {rows.map((item) => <tr key={`${item.kind}-${item.name}`} className={item.name === selected ? styles.rowSelected : ""} onClick={() => onOpen(item.name)} title={item.name}>
        <td>{item.kind === "baseline" ? <span className={styles.baselineTag}>★ {item.label ?? "baseline"}</span> : <span className={styles.tag}>run</span>}</td>
        <td>{SUITE_NAMES[item.suite_id ?? ""] ?? item.suite_id ?? "—"}</td>
        <td>{item.strategy ?? "—"}{item.provider ? ` · ${item.provider}` : ""}</td>
        <td>{formatWhen(item)}</td>
        <td>{typeof item.headline_value === "number" ? `${(item.headline_value * 100).toFixed(1)}%` : "—"}{typeof item.passed === "number" ? ` (${item.passed}/${item.case_count})` : ""}</td>
        <td>{item.fixture_is_current ? "current" : <span className={styles.muted}>older</span>}</td>
      </tr>)}
      {rows.length === 0 && <tr><td colSpan={6}>No saved runs match these filters.</td></tr>}
    </tbody></table></div>;
}

function ComparisonPanel({ comparison }: { comparison: Comparison }) {
  const label = { regressed: "Regressed", improved: "Improved", rank_changed: "Rank changed" };
  return <section className={styles.comparison}><h3>Compared with {comparison.baseline}</h3><small>{comparison.strategies.join(" → ")}</small>{comparison.warnings.map((warning) => <p key={warning} className={styles.warning}>{warning}</p>)}<div className={styles.metricGrid}>{Object.entries(comparison.metrics).map(([name, value]) => <div key={name}><small>{name.replaceAll("_", " ")}</small><strong>{value.delta > 0 ? "+" : ""}{Number.isInteger(value.delta) ? value.delta : `${(value.delta * 100).toFixed(1)} pp`}</strong><small>{Number.isInteger(value.baseline) ? value.baseline : value.baseline.toFixed(3)} → {Number.isInteger(value.candidate) ? value.candidate : value.candidate.toFixed(3)}</small></div>)}</div>
    <div className={styles.resultCases}>{comparison.changes.length === 0 && <p>No per-case changes.</p>}{comparison.changes.map((item) => <article key={item.case_id} className={item.change === "regressed" ? styles.resultFail : styles.resultPass}><div><strong>{item.case_id}</strong><span>{label[item.change]}</span></div><p>{item.question}</p><small>{item.baseline_outcome ? `outcome ${item.baseline_outcome} → ${item.candidate_outcome}` : `rank ${item.baseline_rank ?? "—"} → ${item.candidate_rank ?? "—"}`}</small></article>)}</div>
    {(comparison.added_case_ids.length > 0 || comparison.removed_case_ids.length > 0) && <small>Added: {comparison.added_case_ids.join(", ") || "none"} · Removed: {comparison.removed_case_ids.join(", ") || "none"}</small>}</section>;
}

function DebugPanel({ result }: { result: DebugResult }) {
  const hasDiagnostics = Boolean(result.diagnostics.validation_error || result.diagnostics.rejected_draft);
  return <section className={styles.results}><div className={styles.answer}><p className={styles.eyebrow}>Safe final response</p><h2>{result.answer.outcome}</h2><p>{result.answer.display_text || "[No display text]"}</p>{result.answer.claims.map((claim) => <div key={claim.text} className={styles.citations}>{claim.citations.map((citation) => <a key={citation.anchor_key} href={citation.source_link} target="_blank" rel="noreferrer">{citation.anchor_key} / {citation.source_title}</a>)}</div>)}</div><div><p className={styles.eyebrow}>Retrieved evidence</p><EvidenceList items={result.retrieved_chunks} /></div>{hasDiagnostics && <details className={styles.diagnostics}><summary>Rejected provider output (local debugging only)</summary><p>{result.diagnostics.validation_error}</p><pre>{JSON.stringify(result.diagnostics.rejected_draft, null, 2)}</pre></details>}</section>;
}
