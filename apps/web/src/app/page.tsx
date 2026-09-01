import styles from "./page.module.css";

export default function Home() {
  return (
    <main className={styles.main}>
      <p className={styles.eyebrow}>TaxRAG / Foundation</p>
      <h1>Source-grounded IRPF answers, built in the open.</h1>
      <p className={styles.summary}>
        The first milestone preserves an approved Receita Federal source before we ask an
        AI model to answer from it.
      </p>
      <dl className={styles.statuses}>
        <div>
          <dt>Frontend</dt>
          <dd>Next.js is running.</dd>
        </div>
        <div>
          <dt>Next</dt>
          <dd>Connect this page to the FastAPI health endpoint.</dd>
        </div>
      </dl>
    </main>
  );
}
