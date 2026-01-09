import { useEffect, useRef, useState, useCallback } from 'react';

/**
 * Custom hook for WebSocket connection with automatic reconnection
 *
 * @param {string} url - WebSocket URL
 * @param {object} options - Configuration options
 * @returns {object} - WebSocket state and methods
 */
export function useWebSocket(url, options = {}) {
  const {
    reconnectInterval = 3000,
    reconnectAttempts = 10,
    onMessage = null,
    onConnect = null,
    onDisconnect = null,
    onError = null,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const [reconnectCount, setReconnectCount] = useState(0);

  const ws = useRef(null);
  const reconnectTimer = useRef(null);
  const shouldReconnect = useRef(true);

  // Connect to WebSocket
  const connect = useCallback(() => {
    try {
      ws.current = new WebSocket(url);

      ws.current.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        setReconnectCount(0);

        if (onConnect) {
          onConnect();
        }
      };

      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setLastMessage(data);

          if (onMessage) {
            onMessage(data);
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      ws.current.onerror = (error) => {
        console.error('WebSocket error:', error);

        if (onError) {
          onError(error);
        }
      };

      ws.current.onclose = () => {
        console.log('WebSocket disconnected');
        setIsConnected(false);

        if (onDisconnect) {
          onDisconnect();
        }

        // Attempt reconnection
        if (shouldReconnect.current && reconnectCount < reconnectAttempts) {
          reconnectTimer.current = setTimeout(() => {
            console.log(`Reconnecting... (attempt ${reconnectCount + 1}/${reconnectAttempts})`);
            setReconnectCount(prev => prev + 1);
            connect();
          }, reconnectInterval);
        }
      };
    } catch (error) {
      console.error('Error creating WebSocket:', error);
    }
  }, [url, reconnectCount, reconnectAttempts, reconnectInterval, onMessage, onConnect, onDisconnect, onError]);

  // Send message via WebSocket
  const sendMessage = useCallback((message) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(message));
      return true;
    } else {
      console.warn('WebSocket is not connected');
      return false;
    }
  }, []);

  // Send command
  const sendCommand = useCallback((command, data = {}) => {
    return sendMessage({
      command,
      data,
    });
  }, [sendMessage]);

  // Disconnect WebSocket
  const disconnect = useCallback(() => {
    shouldReconnect.current = false;

    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
    }

    if (ws.current) {
      ws.current.close();
      ws.current = null;
    }

    setIsConnected(false);
  }, []);

  // Connect on mount
  useEffect(() => {
    connect();

    // Cleanup on unmount
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    isConnected,
    lastMessage,
    reconnectCount,
    sendMessage,
    sendCommand,
    disconnect,
  };
}

export default useWebSocket;
