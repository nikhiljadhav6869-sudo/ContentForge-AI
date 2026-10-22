"use client";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main className="standalone">
      <h1>Something interrupted the workspace.</h1>
      <p>Your saved workflows are kept on the server.</p>
      <button onClick={reset} className="button button-primary">
        Try again
      </button>
    </main>
  );
}
