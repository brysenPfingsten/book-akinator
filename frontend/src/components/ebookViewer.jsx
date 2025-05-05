import React, { useState, useEffect } from 'react';
import { speakText } from '../audioPlayer';

const EbookViewer = ({ jobId }) => {
  const [sections, setSections] = useState([]);
  const [selected, setSelected] = useState(null);
  const [text, setText] = useState('');
  const basePath = `${import.meta.env.VITE_API_URL}/ebooks/b4e00eb6-367c-4495-8c2a-7cea89de1b8d/parsed`;

  useEffect(() => {
    fetch(`${basePath}/index.json`)
      .then(res => res.json())
      .then(setSections)
      .catch(err => console.error('Error loading index.json:', err));
  }, [jobId]);

  useEffect(() => {
    if (selected) {
      fetch(`${basePath}/${selected}`)
        .then(res => res.text())
        .then(setText)
        .catch(err => console.error('Error loading section:', err));
    }
  }, [selected, basePath]);

  const handleSpeak = () => {
    speakText(text);
  };

  return (
    <div className="ebook-viewer">
      <div className="ebook-header">
        <h2>eBook Sections</h2>
        {text && (
          <button onClick={handleSpeak} className="speak-button">
            🔊 Speak
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
