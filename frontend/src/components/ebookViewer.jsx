import React, { useState, useEffect } from 'react';
import { speakText, stopSpeaking } from '../audioPlayer';

const EbookViewer = ({ jobId = 'b4e00eb6-367c-4495-8c2a-7cea89de1b8d'}) => {
  const [sections, setSections] = useState([]);
  const [selected, setSelected] = useState(null);
  const [text, setText] = useState('');
  const [speaking, setSpeaking] = useState(false);
  const basePath = `${import.meta.env.VITE_API_URL}/ebooks/${jobId}/parsed`;

  useEffect(() => {
    if (!jobId) return;
  
    let isMounted = true;
    const pollInterval = 2000; // 2 seconds
  
    const checkForIndex = async () => {
      try {
        const res = await fetch(`${basePath}/index.json`);
        if (!res.ok) throw new Error("index.json not ready");
  
        const data = await res.json();
        if (Array.isArray(data) && isMounted) {
          setSections(data);
        } else {
          console.error("Invalid index.json structure:", data);
        }
      } catch (err) {
        setTimeout(checkForIndex, pollInterval); // retry
      }
    };
  
    checkForIndex();
  
    return () => {
      isMounted = false;
    };
  }, [jobId]);
  

  useEffect(() => {
    if (selected) {
      fetch(`${basePath}/${selected}`)
        .then(res => res.text())
        .then(setText)
        .catch(err => console.error('Error loading section:', err));
    }
  }, [selected, basePath]);

  const handleSpeak = async () => {
    if (speaking) {
      stopSpeaking();
      setSpeaking(false);
    } else {
      setSpeaking(true);
      await speakText(text);
      setSpeaking(false);
    }
  };

  return (
    <div className="ebook-viewer">
      <div className="ebook-header">
        <h2>eBook Sections</h2>
        {text && (
          <button
            onClick={handleSpeak}
            className={`speak-button ${speaking ? 'stop' : ''}`}
            style={{
              backgroundColor: speaking ? 'red' : '',
              color: speaking ? 'white' : '',
            }}
          >
            {speaking ? '⏹️ Stop' : '🔊 Speak'}
          </button>
        )}
      </div>
      <div className="ebook-layout">
        <aside className="section-list">
          {sections.map((filename) => (
            <button
              key={filename}
              onClick={() => setSelected(filename)}
              className={`section-button ${selected === filename ? 'active' : ''}`}
            >
              {filename.replace('.txt', '')}
            </button>
          ))}
        </aside>
        <main className="text-display">
          <div className="text-content">{text}</div>
        </main>
      </div>
    </div>
  );
};

export default EbookViewer;
