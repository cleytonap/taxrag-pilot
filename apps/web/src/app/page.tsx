"use client";

import { FormEvent, useEffect, useState } from "react";
import styles from "./page.module.css";

type EvalCase = { case_id: string; question: string; acceptable_anchor_keys: string[]; preferred_anchor_keys?: string[]; expected_abstain?: boolean; human_review_criteria?: string[] };
type Suite = { id: "retrieval" | "answer"; label: string; path: string; case_count: number; cases: EvalCase[] };
type Fixture = { id: Suite["id"]; path: string; content: string; sha256: string; cases: EvalCase[] };
type Artifact = { name: string; size_bytes: number; modified_at: number; format: string };
type Evidence = { rank?: number; chunk_id: string; anchor_key: string; anchor_title: string; source_title: string; source_link: string; score?: number; excerpt: string };
type DebugResult = { answer: { display_text: string; outcome: string; claims: Array<{ text: string; citations: Array<{ anchor_key: string; source_title: string; source_link: string }> }> }; retrieved_chunks: Evidence[]; diagnostics: { validation_error: string | null; rejected_draft: unknown | null } };
type EvalOutcome = { artifact_name: string; summary: Record<string, number | null>; cases: Array<{ case_id: string; question: string; passed: boolean; acceptable_anchor_keys: string[]; preferred_anchor_keys?: string[]; acceptable_rank?: number | null; preferred_rank?: number | null; expected_abstain?: boolean; actual_outcome?: string; cited_acceptable_anchor_keys?: string[]; human_review_criteria?: string[]; answer?: { display_text: string }; retrieved_evidence: Evidence[] }> };

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10_000);
  try {
    const response = await fetch(`/api/taxrag${path}`, { ...init, signal: controller.signal, headers: { "Content-Type": "application/json", ...init?.headers } });
    const body = (await response.json()) as T & { detail?: string };
    if (!response.ok) throw new Error(body.detail ?? `Request failed (${response.status})`);
    return body;
  } catch (error) {
    if (controller.signal.aborted) throw new Error(`Request to ${path} timed out after 10 seconds.`);
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
      const outcome = await api<EvalOutcome>(`/api/evals/suites/${selectedSuite}/run`, { method: "POST", body: JSON.stringify({ strategy: suiteStrategy, provider: selectedSuite === "answer" ? suiteProvider : "fake", confirm_paid_request: confirmSuitePaid }) });
      setSuiteOutcome(outcome); setArtifacts(await refreshArtifacts()); setNotice(`Run saved to var/eval-runs/${outcome.artifact_name}.`);
    } catch (error) { setNotice(error instanceof Error ? error.message : "Suite run failed."); }
    finally { setBusy(false); }
  }
  async function openArtifact(name: string) {
    try { const artifact = await api<{ name: string; content: string }>(`/api/evals/artifacts/${encodeURIComponent(name)}`); setArtifactContent(artifact.content); }
    catch (error) { setNotice(error instanceof Error ? error.message : "Artifact could not be opened."); }
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
    const anchors = expectedAbstain && selectedSuite === "answer" ? [] : selectedAnchors;
    if (selectedSuite === "retrieval" && anchors.length === 0) { setNotice("Select at least one acceptable anchor before saving this retrieval case."); return; }
    if (selectedSuite === "answer" && !expectedAbstain && anchors.length === 0) { setNotice("Select an acceptable anchor, or mark expected abstention."); return; }
    const prefix = selectedSuite === "retrieval" ? "lex" : "answer";
    const nextNumber = Math.max(0, ...fixture.cases.map((item) => Number(item.case_id.match(/(\d+)$/)?.[1] ?? 0))) + 1;
    const record: Record<string, unknown> = { id: `${prefix}-${String(nextNumber).padStart(3, "0")}`, question: question.trim(), acceptable_anchor_keys: anchors };
    if (selectedSuite === "retrieval") record.preferred_anchor_keys = preferredAnchor && anchors.includes(preferredAnchor) ? [preferredAnchor] : [];
    else {
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

  const suiteNeedsPaidRequest = suiteStrategy === "semantic" || suiteStrategy === "hybrid_rrf" || (selectedSuite === "answer" && suiteProvider === "openai");
  const questionNeedsPaidRequest = strategy === "semantic" || strategy === "hybrid_rrf" || provider === "openai";
  const activeSuite = suites.find((item) => item.id === selectedSuite);

  return <main className={styles.main}>
    <section className={styles.hero}><p className={styles.eyebrow}>TaxRAG / Local developer tool</p><h1>Eval Workshop</h1><p>Run suites, inspect failures, and turn diagnostic queries into reviewable test cases.</p></section>
    <nav className={styles.tabs} aria-label="Eval Manager sections"><button className={tab === "suites" ? styles.active : ""} onClick={() => setTab("suites")}>Suites & cases</button><button className={tab === "archive" ? styles.active : ""} onClick={() => setTab("archive")}>Run archive</button><button className={tab === "question" ? styles.active : ""} onClick={() => setTab("question")}>Question lab</button></nav>
    <div className={styles.notice} role="status" aria-live="polite"><span>{notice}</span>{!workspaceLoading && notice.startsWith("Could not load the local workspace:") && <button className={styles.retry} onClick={retryWorkspaceLoad}>Retry connection</button>}</div>
    {tab === "suites" && <section className={styles.workspace}>
      <aside className={styles.sidebar}><h2>Versioned suites</h2>{suites.map((suite) => <button key={suite.id} className={selectedSuite === suite.id ? styles.suiteSelected : styles.suite} onClick={() => changeSuite(suite.id)}><strong>{suite.label}</strong><span>{suite.case_count} cases</span><small>{suite.path}</small></button>)}</aside>
      <div className={styles.editor}>
        <div className={styles.sectionTitle}><div><p className={styles.eyebrow}>Run and review</p><h2>{activeSuite?.label ?? "Evaluation suite"}</h2><small>{fixture?.path}</small></div><button className={styles.primary} disabled={busy || !fixture || (suiteNeedsPaidRequest && !confirmSuitePaid)} onClick={runSelectedSuite}>{busy ? "Running suite…" : "Run suite"}</button></div>
        <div className={styles.runControls}><label>Retrieval strategy<select value={suiteStrategy} onChange={(event) => setSuiteStrategy(event.target.value)}><StrategyOptions /></select></label>{selectedSuite === "answer" && <label>Answer provider<select value={suiteProvider} onChange={(event) => setSuiteProvider(event.target.value)}><option value="fake">Deterministic fake (no API)</option><option value="openai">OpenAI (billable)</option></select></label>}</div>
        {suiteNeedsPaidRequest && <label className={styles.consent}><input type="checkbox" checked={confirmSuitePaid} onChange={(event) => setConfirmSuitePaid(event.target.checked)} /> I confirm this may send official chunks to OpenAI and incur API cost.</label>}
        <p className={styles.warning}>Local only: saving fixtures changes Git-tracked JSONL. Runs are saved under <code>var/eval-runs/</code>.</p>
        {suiteOutcome && <SuiteResult result={suiteOutcome} onOpenArtifact={() => { setTab("archive"); void openArtifact(suiteOutcome.artifact_name); }} />}
        <details className={styles.fixtureDetails}><summary>Edit raw fixture JSONL</summary><div className={styles.sectionTitle}><span>Validate before saving</span><button className={styles.secondary} disabled={busy || !fixture} onClick={() => void saveFixture()}>Validate & save fixture</button></div><textarea aria-label="JSONL fixture" value={fixture?.content ?? ""} onChange={(event) => fixture && setFixture({ ...fixture, content: event.target.value })} /></details>
        <h3>Cases ({fixture?.cases.length ?? 0})</h3><div className={styles.caseGrid}>{fixture?.cases.map((item) => <article key={item.case_id}><code>{item.case_id}</code><p>{item.question}</p><small>{item.acceptable_anchor_keys.join(" · ") || "No support anchors (expected abstention)"}</small></article>)}</div>
      </div>
    </section>}
    {tab === "archive" && <section className={styles.archive}><div><p className={styles.eyebrow}>Read-only local history</p><h2>Saved run artifacts</h2><p>Every run records its fixture hash, strategy, source versions, summary, and per-case evidence.</p></div><div className={styles.artifactList}>{artifacts.map((artifact) => <button key={artifact.name} onClick={() => void openArtifact(artifact.name)}><strong>{artifact.name}</strong><span>{new Date(artifact.modified_at * 1000).toLocaleString()} · {Math.ceil(artifact.size_bytes / 1024)} KB</span></button>)}</div><pre className={styles.artifactContent}>{artifactContent || "Select a saved run to inspect its complete JSON artifact."}</pre></section>}
    {tab === "question" && <section className={styles.questionLab}><div><p className={styles.eyebrow}>One explicit run</p><h2>Question lab</h2><p>Run a diagnostic, inspect evidence, then add the query to a suite without retyping it.</p></div><form onSubmit={submitQuestion} className={styles.questionForm}><label>Question<textarea value={question} onChange={(event) => setQuestion(event.target.value)} /></label><div className={styles.runControls}><label>Retrieval strategy<select value={strategy} onChange={(event) => setStrategy(event.target.value)}><StrategyOptions /></select></label><label>Answer provider<select value={provider} onChange={(event) => setProvider(event.target.value)}><option value="fake">Deterministic fake (no API call)</option><option value="openai">OpenAI (billable)</option></select></label></div>{questionNeedsPaidRequest && <label className={styles.consent}><input type="checkbox" checked={confirmPaid} onChange={(event) => setConfirmPaid(event.target.checked)} /> I understand the question and chunks may be sent to OpenAI and incur cost.</label>}<button className={styles.primary} disabled={busy || (questionNeedsPaidRequest && !confirmPaid)}>{busy ? "Running…" : "Run diagnostic"}</button></form>
      {debugResult && <><DebugPanel result={debugResult} /><section className={styles.addCase}><p className={styles.eyebrow}>Add this query to a suite</p><h3>Turn diagnostic into a test case</h3><label>Target suite<select value={selectedSuite} onChange={(event) => changeSuite(event.target.value as Suite["id"])}><option value="retrieval">Lexical retrieval baseline</option><option value="answer">Cited-answer development</option></select></label>{selectedSuite === "answer" && <label className={styles.consent}><input type="checkbox" checked={expectedAbstain} onChange={(event) => setExpectedAbstain(event.target.checked)} /> Expect the answer provider to abstain</label>}
        {!(selectedSuite === "answer" && expectedAbstain) && <div className={styles.anchorPicker}><strong>Select acceptable support chunks</strong>{debugResult.retrieved_chunks.map((chunk) => <label key={chunk.chunk_id}><input type="checkbox" checked={selectedAnchors.includes(chunk.anchor_key)} onChange={(event) => setSelectedAnchors((current) => event.target.checked ? [...new Set([...current, chunk.anchor_key])] : current.filter((key) => key !== chunk.anchor_key))} /><span>{chunk.anchor_key} · {chunk.anchor_title}</span></label>)}{debugResult.retrieved_chunks.length === 0 && <p>No chunks returned. Choose expected abstention for an answer case.</p>}</div>}
        {selectedSuite === "retrieval" && <label>Preferred anchor (optional)<select value={preferredAnchor} onChange={(event) => setPreferredAnchor(event.target.value)}><option value="">No preferred source</option>{selectedAnchors.map((anchor) => <option key={anchor} value={anchor}>{anchor}</option>)}</select></label>}{selectedSuite === "answer" && <label>Human review criteria (one per line)<textarea value={reviewCriteria} onChange={(event) => setReviewCriteria(event.target.value)} placeholder="Directly answers the question.&#10;Uses an acceptable official citation." /></label>}<button className={styles.secondary} disabled={busy || !fixture} onClick={() => void addDiagnosticCase()}>Validate and add to {selectedSuite} suite</button></section></>}
    </section>}
  </main>;
}

function StrategyOptions() { return <><option value="lexical">Lexical</option><option value="lexical_authority">Lexical + authority</option><option value="semantic">Semantic</option><option value="hybrid_rrf">Hybrid RRF</option></>; }

function EvidenceList({ items }: { items: Evidence[] }) {
  return <div className={styles.evidence}>{items.map((item, index) => <details key={`${item.chunk_id}-${index}`}><summary>{item.rank ? `#${item.rank} ` : ""}{item.anchor_key}{item.score !== undefined && <span>score {item.score.toFixed(4)}</span>}</summary><p><a href={item.source_link} target="_blank" rel="noreferrer">Open {item.source_title} · {item.anchor_title}</a></p><p>{item.excerpt}</p></details>)}</div>;
}

function SuiteResult({ result, onOpenArtifact }: { result: EvalOutcome; onOpenArtifact: () => void }) {
  const metrics = Object.entries(result.summary).filter(([, value]) => typeof value === "number");
  return <section className={styles.suiteResults}><div className={styles.sectionTitle}><div><p className={styles.eyebrow}>Saved run · {result.artifact_name}</p><h3>Run summary</h3></div><button className={styles.secondary} onClick={onOpenArtifact}>Open JSON artifact</button></div><div className={styles.metricGrid}>{metrics.map(([name, value]) => <div key={name}><small>{name.replaceAll("_", " ")}</small><strong>{name.includes("rate") && value !== null ? `${(value * 100).toFixed(0)}%` : value}</strong></div>)}</div><h3>Case results</h3><div className={styles.resultCases}>{result.cases.map((item) => <article key={item.case_id} className={item.passed ? styles.resultPass : styles.resultFail}><div><strong>{item.case_id}</strong><span>{item.passed ? "Pass" : "Needs review"}</span></div><p>{item.question}</p>{item.acceptable_rank !== undefined && <small>Acceptable rank: {item.acceptable_rank ?? "outside top 3"}{item.preferred_anchor_keys?.length ? ` · preferred rank: ${item.preferred_rank ?? "outside top 3"}` : ""}</small>}{item.actual_outcome && <small>Outcome: {item.actual_outcome} · acceptable citation: {item.cited_acceptable_anchor_keys?.join(", ") || "none"}</small>}{item.answer?.display_text && <p>{item.answer.display_text}</p>}{item.human_review_criteria?.length ? <ul>{item.human_review_criteria.map((criterion) => <li key={criterion}>{criterion}</li>)}</ul> : null}{item.retrieved_evidence?.length ? <EvidenceList items={item.retrieved_evidence} /> : null}</article>)}</div></section>;
}

function DebugPanel({ result }: { result: DebugResult }) {
  const hasDiagnostics = Boolean(result.diagnostics.validation_error || result.diagnostics.rejected_draft);
  return <section className={styles.results}><div className={styles.answer}><p className={styles.eyebrow}>Safe final response</p><h2>{result.answer.outcome}</h2><p>{result.answer.display_text || "[No display text]"}</p>{result.answer.claims.map((claim) => <div key={claim.text} className={styles.citations}>{claim.citations.map((citation) => <a key={citation.anchor_key} href={citation.source_link} target="_blank" rel="noreferrer">{citation.anchor_key} / {citation.source_title}</a>)}</div>)}</div><div><p className={styles.eyebrow}>Retrieved evidence</p><EvidenceList items={result.retrieved_chunks} /></div>{hasDiagnostics && <details className={styles.diagnostics}><summary>Rejected provider output (local debugging only)</summary><p>{result.diagnostics.validation_error}</p><pre>{JSON.stringify(result.diagnostics.rejected_draft, null, 2)}</pre></details>}</section>;
}
