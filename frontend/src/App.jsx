import React, { useState, useRef, useEffect } from 'react';
import './App.css';
import { useJobStatus } from './hooks/useJobStatus';
import EbookViewer from './components/ebookViewer';

export default function App() {
  const [isRecording, setIsRecording] = useState(false);
  const [isUnsure, setIsUnsure] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [pullTrigger, setPullTrigger] = useState(0);
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
      download_book();
      break;
      default:
      break;
    }
  };
  
  const download_book = async () => {
    const endpoint = `${import.meta.env.VITE_API_URL}/download_book/${jobId}`;
    const res = await fetch(endpoint, {
      method: 'POST'
    });
    const data = await res.json()
    console.log(data);
    const newJobId = (data.job_id || data.jobId || jobId).toLowerCase();
    setJobId(newJobId);
    setPullTrigger((n) => n + 1);
  }
  
  // Use custom hook to poll job status
  const { phase, result, transcript } = useJobStatus(jobId, import.meta.env.VITE_API_URL, 2000, pullTrigger);
  
  useEffect(() => {
    switch (phase) {
      case 'guessed':
      log('Job completed, updating guess');
      setIsProcessing(false);
      process_guess(result);
      break;
      case 'downloading_list':
      log('[IRC] Fetching download list  ...')
      break;
      case 'downloaded_list':
      log('[IRC] Downloaded list.')
      download_book();
      break;
      case 'downloading_book':
      log('[IRC] Downloading book ...')
      break;
      case 'downloaded_book':
      log('[IRC] Downloaded book.')
      break;
      case 'converting_book':
      log('[CONV] Converting book ...')
      break;
      case 'converted_book':
      log('[CONV] Converted book.');
      break;
      case 'failed':
      setIsProcessing(false);
      log(`[ERROR] ${result}`);
      break;
      default:
      break;
    }
  }, [phase, result]);
  
  useEffect(() => {
    if (transcript) {
      log(`[STT]: ${transcript.trim()}`);
    }
  }, [transcript]);
  
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
    setIsProcessing(true);
    
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
        setPullTrigger((n) => n + 1);
        
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

  useEffect(() => {
    const container = document.querySelector('.main-layout');
    const leftPanel = document.querySelector('.left-panel');
    const rightPanel = document.querySelector('.right-panel');
    
    if (!container || !leftPanel || !rightPanel) return;
  
    const resizeHandle = document.createElement('div');
    resizeHandle.style.position = 'absolute';
    resizeHandle.style.width = '8px';
    resizeHandle.style.height = '100%';
    resizeHandle.style.background = '#334155';
    resizeHandle.style.cursor = 'col-resize';
    resizeHandle.style.zIndex = '10';
    resizeHandle.style.left = `${(leftPanel.offsetWidth / container.offsetWidth) * 100}%`;
  
    container.appendChild(resizeHandle);
  
    let isDragging = false;
    let startX = 0;
    let startLeftWidth = 0;
  
    const startDragging = (e) => {
      isDragging = true;
      startX = e.clientX;
      startLeftWidth = leftPanel.offsetWidth;
      document.addEventListener('mousemove', onDrag);
      document.addEventListener('mouseup', stopDragging);
      resizeHandle.style.backgroundColor = '#4a5568';
    };
  
    const onDrag = (e) => {
      if (!isDragging) return;
      
      const containerRect = container.getBoundingClientRect();
      const deltaX = e.clientX - startX;
      const newLeftWidth = startLeftWidth + deltaX;
      const minWidth = 300;
      const maxWidth = containerRect.width * 0.6;
  
      const clampedWidth = Math.min(Math.max(newLeftWidth, minWidth), maxWidth);
      const percent = (clampedWidth / containerRect.width) * 100;
  
      leftPanel.style.flex = `0 0 ${percent}%`;
      rightPanel.style.flex = `0 0 ${100 - percent}%`;
      resizeHandle.style.left = `${percent}%`;
    };
  
    const stopDragging = () => {
      isDragging = false;
      resizeHandle.style.backgroundColor = '#334155';
      document.removeEventListener('mousemove', onDrag);
      document.removeEventListener('mouseup', stopDragging);
    };
  
    resizeHandle.addEventListener('mousedown', startDragging);
  
    return () => {
      container.removeChild(resizeHandle);
      document.removeEventListener('mousemove', onDrag);
      document.removeEventListener('mouseup', stopDragging);
    };
  }, []);
  
  return (
    <div className="app-container">
      <h1 className="app-title">Academicnator</h1>
      <div className="main-layout">
        <div className="left-panel">
          <button
            onClick={handleRecordButtonClick}
            disabled={isProcessing}
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
  
          <div className="logs-container">
            <button
              onClick={() => setShowLogs((prev) => !prev)}
              className="toggle-logs"
            >
              {showLogs ? 'Hide Logs' : 'Show Logs'}
            </button>
            {showLogs && (
              <div className="logs-panel">
                {logs.map((entry, idx) => (
                  <div key={idx} className="log-entry">{entry}</div>
                ))}
              </div>
            )}
          </div>
        </div>
  
        <div className="right-panel">
          <EbookViewer jobId={jobId} />
        </div>
      </div>
    </div>
  );
  
}