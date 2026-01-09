import AgentStatusGrid from './AgentStatusGrid';
import AudioMeters from './AudioMeters';
import PerformanceMonitor from './PerformanceMonitor';
import SyncStatus from './SyncStatus';

function Dashboard() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">System Dashboard</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <AgentStatusGrid />
        </div>

        <div className="space-y-6">
          <AudioMeters />
          <SyncStatus />
        </div>
      </div>

      <div>
        <PerformanceMonitor />
      </div>
    </div>
  );
}

export default Dashboard;
