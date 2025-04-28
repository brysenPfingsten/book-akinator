import React, { useState, useRef, useEffect } from 'react';
import './App.css';
import { useJobStatus } from './hooks/useJobStatus';

export default function App() {
  const [isRecording, setIsRecording] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [guess, setGuess] = useState('');
  const [logs, setLogs] = useState([]);
  const [showLogs, setShowLogs] = useState(false);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  const log = (message) => {
    setLogs((prev) => [...prev, `${new Date().toLocaleTimeString()}: ${message}`]);
  };

  // Use custom hook to poll job status
  const { status, result, transcript } = useJobStatus(jobId, import.meta.env.VITE_API_URL);

  useEffect(() => {
    if (!jobId) return;
    log(`Status update: ${status}`);

    console.log(transcript)
    if (transcript) {
      log(`[BACKEND][TRANSCRIPTION]: ${transcript.trim()}`);
      setGuess(transcript.trim()); 
    }
    if (status === 'completed') {
      log('Job completed, updating guess');
      setGuess(JSON.stringify(result));
    }
    if (status === 'failed') {
      log('Job failed');
    }
  }, [status, jobId, result, transcript ]);

  const handleStart = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      mediaRecorderRef.current.ondataavailable = (e) => {
        audioChunksRef.current.push(e.data);
      };

      mediaRecorderRef.current.start();
      setIsRecording(true);
      log('Recording started');
    } catch (err) {
      log(`Could not start recording: ${err.message}`);
    }
  };

  const handleStop = () => {
    if (!mediaRecorderRef.current) return;

    mediaRecorderRef.current.onstop = async () => {
      log('Recording stopped, preparing payload');
      const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
      audioChunksRef.current = [];

      log('Sending audio to backend');
      const form = new FormData();
      form.append('file', blob, 'recording.webm');

      try {
        const res = await fetch(`${import.meta.env.VITE_API_URL}/recognize`, {
          method: 'POST',
          body: form,
        });
        const { job_id } = await res.json();
        log(`Job created: ${job_id}`);
        setJobId(job_id);
      } catch (err) {
        log(`Error creating job: ${err.message}`);
      }
    };

    mediaRecorderRef.current.stop();
    setIsRecording(false);
  };

  return (
    <div className="app-container">
      <h1 className="app-title">Voice-to-Book</h1>

      <button
        onClick={isRecording ? handleStop : handleStart}
        className={`button ${isRecording ? 'button--stop' : 'button--start'}`}
      >
        {isRecording ? 'Stop Recording' : 'Start Recording'}
      </button>

      <div className="guess">
        <h2 className="guess-title">LLM Guess / Result:</h2>
        <div className="guess-box">{guess || '–'}</div>
      </div>

      <div>
        <button
          onClick={() => setShowLogs((prev) => !prev)}
          className="toggle-logs"
        >
          {showLogs ? 'Hide Logs' : 'Show Logs'}
        </button>
        {showLogs && (
          <div className="logs-panel">
            {logs.map((entry, idx) => (
              <div key={idx}>{entry}</div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
