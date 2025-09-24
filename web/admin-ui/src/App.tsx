import React from 'react';
import TestConsole from '@/components/test-console/TestConsole';
import './App.css';

function App() {
  return (
    <div className="min-h-screen bg-background">
      <div className="container mx-auto py-8">
        <TestConsole />
      </div>
    </div>
  );
}

export default App;