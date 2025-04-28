import { useState, useEffect, useRef } from 'react';

/**
* Custom hook to poll a job status endpoint until completion.
* @param {string|null} jobId - The ID of the job to poll.
* @param {string} apiUrl - Base URL for the API (no trailing slash).
* @param {number} intervalMs - Polling interval in milliseconds.
* @returns {{ phase: string, result: object|null, transcript: string }}
*/
export function useJobStatus(jobId, apiUrl, intervalMs = 2000) {
    const [phase, setPhase] = useState('idle');
    const [result, setResult] = useState(null);
    const [transcript, setTranscript] = useState('');
    const timerRef = useRef(null);
    
    useEffect(() => {
        if (!jobId) return;
        setPhase('processing');
        
        const poll = async () => {
            try {
                const res = await fetch(`${apiUrl}/status/${jobId}`);
                const data = await res.json();
                console.log('[DEBUG] Polled data:', data);
                
                if (data.phase) {
                    setPhase(data.phase);
                }
                
                if (data.transcription && data.transcription !== transcript) {
                    setTranscript(data.transcription);
                }
                
                if (data.phase === 'guessed' && data.guess) {
                    setResult(data.guess);
                    clearInterval(timerRef.current);
                } else if (data.phase === 'failed') {
                    clearInterval(timerRef.current);
                }
            } catch (err) {
                console.error('Polling error:', err);
                clearInterval(timerRef.current);
            }
        };
        
        timerRef.current = setInterval(poll, intervalMs);
        poll();
        
        return () => clearInterval(timerRef.current);
    }, [jobId, apiUrl, intervalMs, transcript]);
    
    return { phase, result, transcript };
}
