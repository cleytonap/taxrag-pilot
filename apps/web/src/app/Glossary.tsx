"use client";

import { useEffect, useState } from "react";
import styles from "./glossary.module.css";

type Value = { value: string; meaning?: string; example?: string; count?: number; suites?: Record<string, number> };
type Field = { name: string; suites: Record<string, string>; type: string; description: string; accepts: string; values?: Value[]; example: string };
type RunTerm = { name: string; group: string; description: string; values?: Value[]; example: string };
type SuiteInfo = { id: string; name: string; file: string; purpose: string; case_count: number; example_record: Record<string, unknown> | null };
type GlossaryData = { suites: SuiteInfo[]; fields: Field[]; run_terms: RunTerm[] };

const FILTERS = [
  { id: "all", label: "All" },
  { id: "retrieval", label: "Retrieval" },
  { id: "generation", label: "Generation" },
  { id: "answer", label: "End-to-end" },
  { id: "run", label: "Run results & metrics" },
];
const SUITE_SHORT: Record<string, string> = { retrieval: "Retrieval", generation: "Generation", answer: "End-to-end" };

/** Searchable reference for every eval fixture field, category value, metric and outcome. */
export default function Glossary() {
  const [data, setData] = useState<GlossaryData | null>(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    fetch("/api/taxrag/api/evals/glossary", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error(`HTTP ${response.status}`))))
      .then(setData)
      .catch((reason: Error) => setError(`Could not load the glossary: ${reason.message}`));
  }, []);

  const needle = query.trim().toLowerCase();
  const matches = (texts: Array<string | undefined>) => !needle || texts.some((text) => text?.toLowerCase().includes(needle));
  const valueTexts = (values?: Value[]) => (values ?? []).flatMap((value) => [value.value, value.meaning, value.example]);

  // Filtering ~30 entries per keystroke is cheap; no memoisation needed.
  const fields = (data?.fields ?? []).filter((field) =>
    filter !== "run" && (filter === "all" || field.suites[filter] !== undefined) &&
    matches([field.name, field.description, field.accepts, field.type, field.example, ...valueTexts(field.values)]));
  const terms = (data?.run_terms ?? []).filter((term) =>
    (filter === "all" || filter === "run") && matches([term.name, term.group, term.description, term.example, ...valueTexts(term.values)]));
  const suites = (data?.suites ?? []).filter((suite) => (filter === "all" || filter === suite.id) && matches([suite.name, suite.purpose, suite.file, suite.id]));

  if (error) return <section className={styles.glossary}><p>{error}</p></section>;
  if (!data) return <section className={styles.glossary}><p>Loading glossary…</p></section>;

  return <section className={styles.glossary}>
    <div className={styles.header}>
      <p className={styles.eyebrow}>Reference</p>
      <h2>Eval glossary</h2>
      <p>What every field in the suite JSONL files means, which values it accepts, and how to read run results. Counts come live from the current fixtures.</p>
      <input className={styles.search} type="search" placeholder="Search fields, values or meanings (e.g. abstain, false-premise, recall)…" value={query} onChange={(event) => setQuery(event.target.value)} aria-label="Search the glossary" />
      <div className={styles.chips}>{FILTERS.map((item) => <button key={item.id} type="button" className={filter === item.id ? styles.chipActive : styles.chip} onClick={() => setFilter(item.id)}>{item.label}</button>)}</div>
      <small>{fields.length} fields · {terms.length} run terms{needle ? ` matching “${query}”` : ""}</small>
    </div>

    {suites.length > 0 && <div className={styles.suiteGrid}>{suites.map((suite) => <article key={suite.id} className={styles.suiteCard}>
      <h3>{suite.name}</h3><code>{suite.file}</code><p>{suite.purpose}</p><small>{suite.case_count} cases · id <code>{suite.id}</code></small>
      {suite.example_record && <details><summary>Example record (first case)</summary><pre>{JSON.stringify(suite.example_record, null, 2)}</pre></details>}
    </article>)}</div>}

    {fields.length > 0 && <><h3 className={styles.sectionHeading}>Fixture fields</h3>
      <nav className={styles.index}>{fields.map((field) => <a key={field.name} href={`#field-${field.name}`}>{field.name}</a>)}</nav>
      <div className={styles.cards}>{fields.map((field) => <article key={field.name} id={`field-${field.name}`} className={styles.card}>
        <div className={styles.cardTitle}><code>{field.name}</code><span className={styles.type}>{field.type}</span></div>
        <div className={styles.badges}>{Object.entries(field.suites).map(([suite, status]) => <span key={suite} className={styles[`badge_${status}`] ?? styles.badge}>{SUITE_SHORT[suite] ?? suite}: {status}</span>)}</div>
        <p>{field.description}</p>
        <p><strong>Accepts:</strong> {field.accepts}</p>
        {field.values && field.values.length > 0 && <ValueTable values={field.values} needle={needle} />}
        <pre className={styles.example}>{field.example}</pre>
      </article>)}</div></>}

    {terms.length > 0 && <><h3 className={styles.sectionHeading}>Run results & metrics</h3>
      <div className={styles.cards}>{terms.map((term) => <article key={term.name} className={styles.card}>
        <div className={styles.cardTitle}><code>{term.name}</code><span className={styles.type}>{term.group}</span></div>
        <p>{term.description}</p>
        {term.values && term.values.length > 0 && <ValueTable values={term.values} needle={needle} />}
        <pre className={styles.example}>{term.example}</pre>
      </article>)}</div></>}

    {fields.length === 0 && terms.length === 0 && suites.length === 0 && <p>Nothing matches “{query}”.</p>}
  </section>;
}

function ValueTable({ values, needle }: { values: Value[]; needle: string }) {
  const showCounts = values.some((value) => value.count !== undefined);
  return <table className={styles.values}><thead><tr><th>Value</th><th>Meaning</th>{showCounts && <th>Cases</th>}</tr></thead><tbody>
    {values.map((value) => {
      const hit = needle && [value.value, value.meaning, value.example].some((text) => text?.toLowerCase().includes(needle));
      const perSuite = value.suites ? Object.entries(value.suites).map(([suite, count]) => `${SUITE_SHORT[suite] ?? suite} ${count}`).join(" · ") : "";
      return <tr key={value.value} className={hit ? styles.hit : ""}>
        <td><code>{value.value}</code></td>
        <td>{value.meaning || <em>no description yet</em>}{value.example && <> <small>e.g. <code>{value.example}</code></small></>}</td>
        {showCounts && <td title={perSuite}>{value.count ?? ""}{perSuite && <small className={styles.perSuite}>{perSuite}</small>}</td>}
      </tr>;
    })}
  </tbody></table>;
}
