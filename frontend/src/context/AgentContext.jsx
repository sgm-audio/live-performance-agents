import { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';

const AgentContext = createContext(null);

export function AgentProvider({ children }) {
  const [agents, setAgents] = useState({});
  const [audioLevels, setAudioLevels] = useState({ inputs: [0, 0], outputs: [0, 0], peaks: [0, 0], clipping: false });
  const [midiMessages, setMidiMessages] = useState([]);
  const [syncStatus, setSyncStatus] = useState({ tempo: 120, playing: false, beat: 0 });
  const [loopStatus, setLoopStatus] = useState({});

  // WebSocket connection
  const {
    isConnected,
    lastMessage,
    sendCommand,
  } = useWebSocket('ws://localhost:8080/ws', {
    onMessage: handleWebSocketMessage,
    onConnect: () => console.log('Connected to agents system'),
    onDisconnect: () => console.log('Disconnected from agents system'),
  });

  // Handle incoming WebSocket messages
  function handleWebSocketMessage(message) {
    const { type, data } = message;

    switch (type) {
      case 'agent_status':
        handleAgentStatus(data);
        break;
      case 'audio_levels':
        setAudioLevels(data);
        break;
      case 'midi_message':
        handleMidiMessage(data);
        break;
      case 'effect_change':
        // Handle effect parameter changes
        break;
      case 'loop_status':
        handleLoopStatus(data);
        break;
      case 'sync_update':
        handleSyncUpdate(data);
        break;
      default:
        console.log('Unknown message type:', type);
    }
  }

  function handleAgentStatus(data) {
    const { agent_id } = data;
    setAgents(prev => ({
      ...prev,
      [agent_id]: data
    }));
  }

  function handleMidiMessage(data) {
    setMidiMessages(prev => [...prev.slice(-49), data]); // Keep last 50 messages
  }

  function handleLoopStatus(data) {
    const { loop_id } = data;
    setLoopStatus(prev => ({
      ...prev,
      [loop_id]: data
    }));
  }

  function handleSyncUpdate(data) {
    setSyncStatus(prev => ({ ...prev, ...data }));
  }

  // Command functions
  const setEffectParameter = useCallback((effectId, parameter, value) => {
    return sendCommand('effect.parameter.set', {
      effect_id: effectId,
      parameter,
      value
    });
  }, [sendCommand]);

  const createMidiMapping = useCallback((deviceId, ccNumber, targetAgent, targetParameter, minValue = 0.0, maxValue = 1.0) => {
    return sendCommand('midi.mapping.create', {
      device_id: deviceId,
      cc_number: ccNumber,
      target_agent: targetAgent,
      target_parameter: targetParameter,
      min_value: minValue,
      max_value: maxValue,
    });
  }, [sendCommand]);

  const deleteMidiMapping = useCallback((mappingId) => {
    return sendCommand('midi.mapping.delete', {
      mapping_id: mappingId
    });
  }, [sendCommand]);

  const startLoopRecording = useCallback((loopId, quantize = true) => {
    return sendCommand('loop.record.start', {
      loop_id: loopId,
      quantize
    });
  }, [sendCommand]);

  const stopLoopRecording = useCallback((loopId) => {
    return sendCommand('loop.record.stop', {
      loop_id: loopId
    });
  }, [sendCommand]);

  const playLoop = useCallback((loopId) => {
    return sendCommand('loop.play', {
      loop_id: loopId
    });
  }, [sendCommand]);

  const stopLoop = useCallback((loopId) => {
    return sendCommand('loop.stop', {
      loop_id: loopId
    });
  }, [sendCommand]);

  const loadPreset = useCallback((presetId) => {
    return sendCommand('preset.load', {
      preset_id: presetId
    });
  }, [sendCommand]);

  const savePreset = useCallback((name, description) => {
    return sendCommand('preset.save', {
      name,
      description
    });
  }, [sendCommand]);

  const startAutomation = useCallback((automationId) => {
    return sendCommand('automation.start', {
      automation_id: automationId
    });
  }, [sendCommand]);

  const stopAutomation = useCallback(() => {
    return sendCommand('automation.stop', {});
  }, [sendCommand]);

  const value = {
    // State
    isConnected,
    agents,
    audioLevels,
    midiMessages,
    syncStatus,
    loopStatus,

    // Commands
    setEffectParameter,
    createMidiMapping,
    deleteMidiMapping,
    startLoopRecording,
    stopLoopRecording,
    playLoop,
    stopLoop,
    loadPreset,
    savePreset,
    startAutomation,
    stopAutomation,
  };

  return (
    <AgentContext.Provider value={value}>
      {children}
    </AgentContext.Provider>
  );
}

export function useAgents() {
  const context = useContext(AgentContext);
  if (!context) {
    throw new Error('useAgents must be used within an AgentProvider');
  }
  return context;
}

export default AgentContext;
