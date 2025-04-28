import React, { useState, useRef, useEffect } from 'react';
import './App.css';
import { useJobStatus } from './hooks/useJobStatus';

export default function App() {
  const [isRecording, setIsRecording] = useState(false);
  const [isUnsure, setIsUnsure] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [guess, setGuess] = useState('');
  const [logs, setLogs] = useState([]);
  const [showLogs, setShowLogs] = useState(false);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  
  const log = (message) => {
    setLogs((prev) => [...prev, `${new Date().toLocaleTimeString()}: ${message}`]);
  };
  
  const process_guess = (guess) => {
    if (!guess.status) { return; }
    switch (guess.status) {
      case "need_clarification":
      log(`[LLM]: Need Clarification.`);
      log(`[LLM]: Follow up: ${guess.question}`);
      setGuess(guess.question);
      setIsUnsure(true);
      break;
      case "confident":
      log(`[LLM]: Confident. "${guess.title}" by ${guess.author}`);
      setGuess(`"${guess.title}" by ${guess.author}`);
      setIsUnsure(false);
      default:
      break;
    }
  };
  
  // Use custom hook to poll job status
  const { phase, result, transcript } = useJobStatus(jobId, import.meta.env.VITE_API_URL);
  
  useEffect(() => {
    if (!jobId) return;
    
    if (transcript) {
      log(`[STT]: ${transcript.trim()}`);
    }
    if (phase === 'guessed') {
      log('Job completed, updating guess');
      process_guess(result);
    }
    if (phase === 'failed') {
      log('Job failed');
    }
  }, [phase, jobId, result, transcript]);
  
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current = [];
      
      mediaRecorderRef.current.ondataavailable = (e) => {
        audioChunksRef.current.push(e.data);
      };
      
      mediaRecorderRef.current.start();
      setIsRecording(true);
      log(isUnsure ? 'Clarification recording started' : 'Recording started');
    } catch (err) {
      log(`Could not start recording: ${err.message}`);
    }
  };
  
  const stopRecording = async () => {
    if (!mediaRecorderRef.current) return;
  
    mediaRecorderRef.current.onstop = async () => {
      log('Recording stopped, preparing payload');
      const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
      audioChunksRef.current = [];
  
      const form = new FormData();
      form.append('file', blob, 'recording.webm');
  
      try {
        const endpoint = isUnsure 
          ? `${import.meta.env.VITE_API_URL}/answer_clarification/${jobId}`
          : `${import.meta.env.VITE_API_URL}/recognize`;
  
        log(`Sending audio to ${isUnsure ? 'clarification' : 'recognition'} endpoint`);
        const res = await fetch(endpoint, {
          method: 'POST',
          body: form,
        });
        const data = await res.json();
  
        // Normalize the job ID to lowercase and update state
        const newJobId = (data.job_id || data.jobId || jobId).toLowerCase();
        setJobId(newJobId);
        log(`Tracking job: ${newJobId}`);
  
        if (isUnsure) {
          log(`Clarification processing started...`);
        }
      } catch (err) {
        log(`Error sending audio: ${err.message}`);
      }
    };
  
    mediaRecorderRef.current.stop();
    setIsRecording(false);
  };
  
  const handleRecordButtonClick = () => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };
  
  return (
    <div className="app-container">
    <h1 className="app-title">Voice-to-Book</h1>
    
    <button
    onClick={handleRecordButtonClick}
    className={`button ${isRecording ? 'button--stop' : 'button--start'}`}
    >
    {isRecording 
      ? 'Stop Recording' 
      : isUnsure 
      ? 'Answer Question' 
      : 'Start Recording'}
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