"use client";

import { useEffect, useState } from "react";

interface ApiStatus {
  status: string;
  db_connected: boolean;
  summary_count: number;
  last_summary_date: string | null;
}

export default function Home() {
  const [data, setData] = useState<ApiStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("http://localhost:8000/api/v1/status")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((json) => {
        setData(json);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8">
      <h1 className="text-4xl font-bold mb-2">Daily Summarizer</h1>
      <h2 className="text-xl text-zinc-500 mb-8">API Status</h2>

      {loading && <p className="text-zinc-400">Loading...</p>}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 max-w-md">
          <p className="text-red-700">Error: {error}</p>
          <p className="text-red-500 text-sm mt-1">
            Make sure the API is running on localhost:8000
          </p>
        </div>
      )}

      {data && (
        <pre className="bg-zinc-100 dark:bg-zinc-900 rounded-lg p-6 max-w-md w-full overflow-auto text-sm">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </main>
  );
}
