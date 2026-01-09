import { useAgents } from '../../context/AgentContext';

function SyncStatus() {
  const { syncStatus } = useAgents();

  return (
    <div className="card">
      <h2 className="card-header">Sync Status</h2>

      <div className="space-y-4">
        <div className="bg-app-bg rounded-md p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-app-text-secondary">Tempo</span>
            <span className="text-2xl font-bold font-mono">
              {syncStatus.tempo.toFixed(2)} <span className="text-sm text-app-text-secondary">BPM</span>
            </span>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-sm text-app-text-secondary">Beat</span>
            <span className="text-lg font-mono">
              {Math.floor(syncStatus.beat / 4) + 1}.{(syncStatus.beat % 4) + 1}
            </span>
          </div>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-sm text-app-text-secondary">Playback</span>
          <div className="flex items-center space-x-2">
            <div className={`w-3 h-3 rounded-full ${syncStatus.playing ? 'bg-app-success animate-pulse' : 'bg-gray-600'}`}></div>
            <span className="text-sm font-medium">
              {syncStatus.playing ? 'Playing' : 'Stopped'}
            </span>
          </div>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-sm text-app-text-secondary">Sync Source</span>
          <span className="text-sm font-mono">Internal</span>
        </div>
      </div>
    </div>
  );
}

export default SyncStatus;
