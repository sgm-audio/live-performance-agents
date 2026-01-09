import { useAgents } from '../../context/AgentContext';

function AgentStatusGrid() {
  const { agents } = useAgents();

  // Define all expected agents
  const allAgents = [
    { id: 'audio_io', name: 'Audio I/O', description: 'Real-time audio interface' },
    { id: 'effects_chain', name: 'Effects Chain', description: 'Audio effects processing' },
    { id: 'midi_control', name: 'MIDI Control', description: 'MIDI device integration' },
    { id: 'looping', name: 'Live Looping', description: 'Loop recording and playback' },
    { id: 'automation', name: 'Automation', description: 'Parameter automation' },
    { id: 'sync_clock', name: 'Sync Clock', description: 'Tempo synchronization' },
    { id: 'visual_lighting', name: 'Visual/Lighting', description: 'DMX and visual control' },
    { id: 'mixing_dynamics', name: 'Mixing/Dynamics', description: 'Channel mixing' },
    { id: 'performance_monitor', name: 'Performance Monitor', description: 'System monitoring' },
    { id: 'backup_redundancy', name: 'Backup/Redundancy', description: 'System redundancy' },
    { id: 'industry_standards', name: 'Industry Standards', description: 'Standards compliance' },
    { id: 'web_interface', name: 'Web Interface', description: 'Frontend communication' },
  ];

  const getAgentStatus = (agentId) => {
    const agent = agents[agentId];
    if (!agent) return { status: 'offline', cpu: 0, warnings: [] };

    return {
      status: agent.status || 'unknown',
      cpu: agent.cpu_usage || 0,
      warnings: agent.warnings || [],
    };
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'running':
        return 'bg-app-success';
      case 'warning':
        return 'bg-app-warning';
      case 'error':
        return 'bg-app-error';
      case 'offline':
        return 'bg-gray-600';
      default:
        return 'bg-gray-500';
    }
  };

  return (
    <div className="card">
      <h2 className="card-header">Agent Status</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {allAgents.map(agent => {
          const status = getAgentStatus(agent.id);

          return (
            <div
              key={agent.id}
              className="bg-app-bg rounded-md p-3 border border-app-border hover:border-app-primary transition-colors cursor-pointer"
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center space-x-2">
                  <div className={`w-3 h-3 rounded-full ${getStatusColor(status.status)}`}></div>
                  <h3 className="font-medium text-sm">{agent.name}</h3>
                </div>

                {status.cpu > 0 && (
                  <span className="text-xs text-app-text-secondary font-mono">
                    {status.cpu.toFixed(1)}%
                  </span>
                )}
              </div>

              <p className="text-xs text-app-text-secondary mb-2">{agent.description}</p>

              {status.warnings.length > 0 && (
                <div className="mt-2 pt-2 border-t border-app-border">
                  <p className="text-xs text-app-warning">
                    {status.warnings.length} warning{status.warnings.length !== 1 ? 's' : ''}
                  </p>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default AgentStatusGrid;
