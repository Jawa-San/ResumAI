import React from 'react';

export function Layout({ children }) {
  console.log('Layout rendering, children:', children);
  
  return (
    <div>
      <nav style={{ padding: '1rem', backgroundColor: '#f0f0f0' }}>
        <h1>ResumAI Test</h1>
        <p>Debug: Layout is working</p>
      </nav>
      <main style={{ padding: '1rem', border: '2px solid red' }}>
        <p>Debug: Children should appear below:</p>
        {children}
        <p>Debug: Children should appear above</p>
      </main>
    </div>
  );
}