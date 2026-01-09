import { useState } from 'react';
import { AgentProvider } from './context/AgentContext';
import Dashboard from './components/Dashboard/Dashboard';
import Header from './components/Header';
import Sidebar from './components/Sidebar';

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');

  return (
    <AgentProvider>
      <div className="min-h-screen flex flex-col">
        <Header />

        <div className="flex-1 flex overflow-hidden">
          <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />

          <main className="flex-1 overflow-auto p-6">
            {activeTab === 'dashboard' && <Dashboard />}
            {activeTab === 'effects' && <div className="card"><h2 className="card-header">Effects Chain</h2><p className="text-app-text-secondary">Coming soon...</p></div>}
            {activeTab === 'midi' && <div className="card"><h2 className="card-header">MIDI Control</h2><p className="text-app-text-secondary">Coming soon...</p></div>}
            {activeTab === 'loops' && <div className="card"><h2 className="card-header">Loop Control</h2><p className="text-app-text-secondary">Coming soon...</p></div>}
            {activeTab === 'automation' && <div className="card"><h2 className="card-header">Automation</h2><p className="text-app-text-secondary">Coming soon...</p></div>}
          </main>
        </div>
      </div>
    </AgentProvider>
  );
}

export default App;
