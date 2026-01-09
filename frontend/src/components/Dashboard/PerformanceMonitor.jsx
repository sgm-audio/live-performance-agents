import { useAgents } from '../../context/AgentContext';

function PerformanceMonitor() {
  const { agents } = useAgents();

  // Calculate total CPU usage
  const totalCPU = Object.values(agents).reduce((sum, agent) => {
    return sum + (agent.cpu_usage || 0);
  }, 0);

  // Count warnings
  const totalWarnings = Object.values(agents).reduce((sum, agent) => {
    return sum + (agent.warnings?.length || 0);
  }, 0);

  // Count agents by status
  const statusCounts = Object.values(agents).reduce((counts, agent) => {
    const status = agent.status || 'offline';
    counts[status] = (counts[status] || 0) + 1;
    return counts;
  }, {});

  return (
    <div className="card">
      <h2 className="card-header">Performance Metrics</h2>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-app-bg rounded-md p-4">
          <div className="text-app-text-secondary text-sm mb-1">Total CPU Usage</div>
          <div className="text-3xl font-bold font-mono">
            {totalCPU.toFixed(1)}%
          </div>
          <div className="mt-2 w-full bg-app-surface rounded-full h-2">
            <div
              className={`h-2 rounded-full transition-all duration-300 ${
                totalCPU > 80 ? 'bg-app-error' : totalCPU > 60 ? 'bg-app-warning' : 'bg-app-success'
              }`}
              style={{ width: `${Math.min(totalCPU, 100)}%` }}
            ></div>
          </div>
        </div>

        <div className="bg-app-bg rounded-md p-4">
          <div className="text-app-text-secondary text-sm mb-1">Running Agents</div>
          <div className="text-3xl font-bold">
            {statusCounts.running || 0}
            <span className="text-lg text-app-text-secondary"> / {Object.keys(agents).length || 12}</span>
          </div>
          <div className="mt-2 text-sm text-app-success">
            {((statusCounts.running || 0) / (Object.keys(agents).length || 12) * 100).toFixed(0)}% online
          </div>
        </div>

        <div className="bg-app-bg rounded-md p-4">
          <div className="text-app-text-secondary text-sm mb-1">Warnings</div>
          <div className={`text-3xl font-bold ${totalWarnings > 0 ? 'text-app-warning' : ''}`}>
            {totalWarnings}
          </div>
          <div className="mt-2 text-sm text-app-text-secondary">
            {totalWarnings > 0 ? 'Needs attention' : 'All clear'}
          </div>
        </div>

        <div className="bg-app-bg rounded-md p-4">
          <div className="text-app-text-secondary text-sm mb-1">Errors</div>
          <div className={`text-3xl font-bold ${statusCounts.error ? 'text-app-error' : ''}`}>
            {statusCounts.error || 0}
          </div>
          <div className="mt-2 text-sm text-app-text-secondary">
            {statusCounts.error ? 'System degraded' : 'All clear'}
          </div>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-app-bg rounded-md p-3 text-center">
          <div className="text-xs text-app-text-secondary mb-1">Avg Latency</div>
          <div className="text-xl font-mono">2.3 <span className="text-xs">ms</span></div>
        </div>

        <div className="bg-app-bg rounded-md p-3 text-center">
          <div className="text-xs text-app-text-secondary mb-1">Buffer Size</div>
          <div className="text-xl font-mono">128 <span className="text-xs">samples</span></div>
        </div>

        <div className="bg-app-bg rounded-md p-3 text-center">
          <div className="text-xs text-app-text-secondary mb-1">Sample Rate</div>
          <div className="text-xl font-mono">48 <span className="text-xs">kHz</span></div>
        </div>

        <div className="bg-app-bg rounded-md p-3 text-center">
          <div className="text-xs text-app-text-secondary mb-1">Buffer Health</div>
          <div className="text-xl font-mono text-app-success">100%</div>
        </div>
      </div>
    </div>
  );
}

export default PerformanceMonitor;
