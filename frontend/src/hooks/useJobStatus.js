import { useState, useEffect, useRef } from 'react';

/**
 * Custom hook to poll a job status endpoint until completion.
 * @param {string|null} jobId - The ID of the job to poll.
 * @param {string} apiUrl - Base URL for the API (no trailing slash).
 * @param {number} intervalMs - Polling interval in milliseconds.
 * @returns {{ status: string, result: object|null }}
 */
export function useJobStatus(jobId, apiUrl, intervalMs = 2000) {
  const [status, setStatus] = useState('idle');
  const [result, setResult] = useState(null);
  const timerRef = useRef(null);

  useEffect(() => {
    if (!jobId) return;
    setStatus('pending');

    const poll = async () => {
      try {
        const res = await fetch(`${apiUrl}/status/${jobId}`);
        const data = await res.json();
        setStatus(data.status);
        if (data.status === 'completed') {
          setResult(data.result);
          clearInterval(timerRef.current);
        } else if (data.status === 'failed') {
          clearInterval(timerRef.current);
        }
      } catch (err) {
        console.error('Polling error:', err);
        clearInterval(timerRef.current);
      }
    };

    // Start polling
    timerRef.current = setInterval(poll, intervalMs);
    // Run immediately once
    poll();

    return () => clearInterval(timerRef.current);
  }, [jobId, apiUrl, intervalMs]);

  return { status, result };
}
