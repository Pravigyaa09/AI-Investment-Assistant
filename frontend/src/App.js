import React, { useState } from 'react';
import './App.css';

function App() {
  const [newsText, setNewsText] = useState('');
  const [submittedText, setSubmittedText] = useState('');

  const handleSubmit = () => {
    setSubmittedText(newsText);
    // (Later) We'll add API call here
  };

  return (
    <div style={{ padding: '2rem', fontFamily: 'Arial' }}>
      <h1>📈 AI Investment Assistant</h1>
      
      <textarea
        rows="6"
        cols="60"
        placeholder="Paste financial news here..."
        value={newsText}
        onChange={(e) => setNewsText(e.target.value)}
        style={{ padding: '1rem', fontSize: '1rem' }}
      />

      <br /><br />

      <button
        onClick={handleSubmit}
        style={{
          padding: '0.5rem 1.5rem',
          fontSize: '1rem',
          cursor: 'pointer',
          backgroundColor: '#007bff',
          color: 'white',
          border: 'none',
          borderRadius: '4px'
        }}
      >
        Analyze
      </button>

      <br /><br />

      {submittedText && (
        <div>
          <h3>📰 Submitted News:</h3>
          <p>{submittedText}</p>
        </div>
      )}
    </div>
  );
}

export default App;
