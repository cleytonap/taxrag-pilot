"use client";

import { FormEvent, useEffect, useState } from "react";
import styles from "./page.module.css";

type Suite = { id: string; label: string; path: string; case_count: number; cases: Array<{ case_id: string; question: string; acceptable_anchor_keys: string[] }> };
type Fixture = { id: string; path: string; content: string; sha256: string; cases: Suite["cases"] };
type Artifact = { name: string; size_bytes: number; modified_at: number; format: string };
type DebugResult = { answer: { display_text: string; outcome: string; claims: Array<{ text: string; citations: Array<{ anchor_key: string; source_title: string; canonical_url: string }> }> }; retrieved_chunks: Array<{ rank: number; anchor_key: string; anchor_title: string; source_title: string; canonical_url: string; score: number; chunk_text: string }>; diagnostics: { validation_error: string | null; rejected_draft: unknown | null } };

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/taxrag${path}`, { ...init, headers: { "Content-Type": "application/json", ...init?.headers } });
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error("Cannot reach the local TaxRAG service. Check that the API and Next.js development servers are running.");
    }
    throw error;
  }
  const body = (await response.json()) as T & { detail?: string };
  if (!response.ok) throw new Error(body.detail ?? `Request failed (${response.status})`);
  return body;
}

export default function Home() {
  const [tab, setTab] = useState<"suites" | "archive" | "question">("suites");
  const [suites, setSuites] = useState<Suite[]>([]);
  const [selectedSuite, setSelectedSuite] = useState("retrieval");
  const [fixture, setFixture] = useState<Fixture | null>(null);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [artifactContent, setArtifactContent] = useState("");
  const [question, setQuestion] = useState("Recebi 30 mil em rendimentos tributáveis em 2025. Devo declarar?");
  const [strategy, setStrategy] = useState("semantic");
  const [provider, setProvider] = useState("fake");
  const [confirmPaid, setConfirmPaid] = useState(false);
  const [debugResult, setDebugResult] = useState<DebugResult | null>(null);
  const [notice, setNotice] = useState("Loading local evaluation workspace...");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void Promise.all([api<{ suites: Suite[] }>("/api/evals/suites"), api<{ artifacts: Artifact[] }>("/api/evals/artifacts")]).then(([suiteResponse, artifactResponse]) => { setSuites(suiteResponse.suites); setArtifacts(artifactResponse.artifacts); setNotice("Local workspace ready. Fixtures remain Git-tracked files."); }).catch((error: Error) => setNotice(`Could not reach the API: ${error.message}`));
  }, []);
  useEffect(() => { void api<Fixture>(`/api/evals/suites/${selectedSuite}/fixture`).then(setFixture).catch((error: Error) => setNotice(error.message)); }, [selectedSuite]);

  async function saveFixture() { if (!fixture) return; setBusy(true); try { const saved = await api<Fixture>(`/api/evals/suites/${fixture.id}/fixture`, { method: "PUT", body: JSON.stringify({ content: fixture.content }) }); setFixture(saved); setNotice(`Saved ${saved.path}. Review the working-tree change before committing.`); } catch (error) { setNotice(error instanceof Error ? error.message : "Fixture could not be saved."); } finally { setBusy(false); } }
  async function openArtifact(name: string) { try { const artifact = await api<{ name: string; content: string }>(`/api/evals/artifacts/${encodeURIComponent(name)}`); setArtifactContent(artifact.content); } catch (error) { setNotice(error instanceof Error ? error.message : "Artifact could not be opened."); } }
  async function submitQuestion(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setBusy(true); setDebugResult(null); try { const result = await api<DebugResult>("/api/evals/debug-answer", { method: "POST", body: JSON.stringify({ question, strategy, provider, confirm_paid_request: confirmPaid }) }); setDebugResult(result); setNotice("Diagnostic result returned. It has not been stored as a run artifact."); } catch (error) { setNotice(error instanceof Error ? error.message : "Question could not be evaluated."); } finally { setBusy(false); } }

  return <main className={styles.main}>
    <section className={styles.hero}><p className={styles.eyebrow}>TaxRAG / Local developer tool</p><h1>Eval Workshop</h1><p>Inspect the evidence chain, not just a pass/fail number.</p></section>
    <nav className={styles.tabs} aria-label="Eval Manager sections"><button className={tab === "suites" ? styles.active : ""} onClick={() => setTab("suites")}>Suites & cases</button><button className={tab === "archive" ? styles.active : ""} onClick={() => setTab("archive")}>Run archive</button><button className={tab === "question" ? styles.active : ""} onClick={() => setTab("question")}>Question lab</button></nav>
    <p className={styles.notice}>{notice}</p>
    {tab === "suites" && <section className={styles.workspace}><aside className={styles.sidebar}><h2>Versioned suites</h2>{suites.map((suite) => <button key={suite.id} className={selectedSuite === suite.id ? styles.suiteSelected : styles.suite} onClick={() => setSelectedSuite(suite.id)}><strong>{suite.label}</strong><span>{suite.case_count} cases</span><small>{suite.path}</small></button>)}</aside><div className={styles.editor}><div className={styles.sectionTitle}><div><p className={styles.eyebrow}>Fixture source</p><h2>{fixture?.path ?? "Loading..."}</h2></div><button className={styles.primary} disabled={busy || !fixture} onClick={saveFixture}>Validate & save</button></div><p className={styles.warning}>Local only: saving changes a Git-tracked JSONL file. Inspect and commit it normally; never expose this endpoint publicly.</p><textarea aria-label="JSONL fixture" value={fixture?.content ?? ""} onChange={(event) => fixture && setFixture({ ...fixture, content: event.target.value })} /><h3>Parsed cases</h3><div className={styles.caseGrid}>{fixture?.cases.map((item) => <article key={item.case_id}><code>{item.case_id}</code><p>{item.question}</p><small>{item.acceptable_anchor_keys?.join(" · ") || "No support anchors (expected abstention)"}</small></article>)}</div></div></section>}
    {tab === "archive" && <section className={styles.archive}><div><p className={styles.eyebrow}>Read-only local history</p><h2>Saved run artifacts</h2><p>These are files already written under <code>var/eval-runs/</code>.</p></div><div className={styles.artifactList}>{artifacts.map((artifact) => <button key={artifact.name} onClick={() => openArtifact(artifact.name)}><strong>{artifact.name}</strong><span>{new Date(artifact.modified_at * 1000).toLocaleString()} · {Math.ceil(artifact.size_bytes / 1024)} KB</span></button>)}</div><pre className={styles.artifactContent}>{artifactContent || "Select a saved artifact to inspect its raw output."}</pre></section>}
    {tab === "question" && <section className={styles.questionLab}><div><p className={styles.eyebrow}>One explicit run</p><h2>Question lab</h2><p>See exactly what was retrieved, returned, and accepted or rejected.</p></div><form onSubmit={submitQuestion} className={styles.questionForm}><label>Question<textarea value={question} onChange={(event) => setQuestion(event.target.value)} /></label><label>Retrieval strategy<select value={strategy} onChange={(event) => setStrategy(event.target.value)}><option value="lexical">Lexical</option><option value="lexical_authority">Lexical + authority</option><option value="semantic">Semantic</option><option value="hybrid_rrf">Hybrid RRF</option></select></label><label>Answer provider<select value={provider} onChange={(event) => setProvider(event.target.value)}><option value="fake">Deterministic fake (no API call)</option><option value="openai">OpenAI (billable)</option></select></label>{provider === "openai" && <label className={styles.confirm}><input type="checkbox" checked={confirmPaid} onChange={(event) => setConfirmPaid(event.target.checked)} /> I understand this sends this question and retrieved official chunks to OpenAI and may incur API cost.</label>}<button className={styles.primary} disabled={busy || (provider === "openai" && !confirmPaid)}>{busy ? "Running..." : "Run diagnostic"}</button></form>{debugResult && <DebugPanel result={debugResult} />}</section>}
  </main>;
}

function DebugPanel({ result }: { result: DebugResult }) {
  const hasDiagnostics = Boolean(result.diagnostics.validation_error || result.diagnostics.rejected_draft);
  return <section className={styles.results}><div className={styles.answer}><p className={styles.eyebrow}>Safe final response</p><h2>{result.answer.outcome}</h2><p>{result.answer.display_text || "[No display text]"}</p>{result.answer.claims.map((claim) => <div key={claim.text} className={styles.citations}>{claim.citations.map((citation) => <a key={citation.anchor_key} href={citation.canonical_url} target="_blank">{citation.anchor_key} / {citation.source_title}</a>)}</div>)}</div><div><p className={styles.eyebrow}>Retrieved evidence</p><div className={styles.evidence}>{result.retrieved_chunks.map((chunk) => <details key={chunk.anchor_key}><summary>#{chunk.rank} {chunk.anchor_key} <span>score {chunk.score.toFixed(4)}</span></summary><p><strong>{chunk.anchor_title}</strong> / {chunk.source_title}</p><p>{chunk.chunk_text}</p></details>)}</div></div>{hasDiagnostics && <details className={styles.diagnostics}><summary>Rejected provider output (local debugging only)</summary><p>{result.diagnostics.validation_error}</p><pre>{JSON.stringify(result.diagnostics.rejected_draft, null, 2)}</pre></details>}</section>;
}
