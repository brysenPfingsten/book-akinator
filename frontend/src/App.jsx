import React, { useState, useRef } from 'react';
import './App.css';

export default function App() {
  const [isRecording, setIsRecording] = useState(false);
  const [guess, setGuess] = useState('');
  const [logs, setLogs] = useState([]);
  const [showLogs, setShowLogs] = useState(false);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  const log = (message) => {
    setLogs((prev) => [...prev, `${new Date().toLocaleTimeString()}: ${message}`]);
  };

  const handleStart = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);

      mediaRecorderRef.current.ondataavailable = (e) => {
        audioChunksRef.current.push(e.data);
      };

      mediaRecorderRef.current.onstop = async () => {
        log('Recording stopped, preparing audio payload');
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        audioChunksRef.current = [];

        log('Sending audio to backend');
        const form = new FormData();
        form.append('file', blob, 'recording.webm');

        try {
          const res = await fetch(import.meta.env.VITE_API_URL + '/recognize', {
            method: 'POST',
            body: form,
          });
          const data = await res.json();
          log(`Received response: ${JSON.stringify(data)}`);
          setGuess(data.book || 'No guess');
        } catch (err) {
          log(`Error fetching guess: ${err.message}`);
        }
      };

      mediaRecorderRef.current.start();
      setIsRecording(true);
      log('Recording started');
    } catch (err) {
      log(`Could not start recording: ${err.message}`);
    }
  };

  const handleStop = () => {
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
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
        <h2 className="guess-title">LLM Guess:</h2>
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
