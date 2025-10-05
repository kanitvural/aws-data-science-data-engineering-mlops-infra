// components/FlightDashboard.tsx
'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import FlightGrid from '@/components/FlightGrid'; 
import Chatbot from '@/components/Chatbot';
import { FlightTableData } from '@/types/flight';
import { Plane, Activity, Clock, AlertTriangle, Wifi, WifiOff, RefreshCw } from 'lucide-react';
import ConnectButton from '@/components/ConnectButton';

export default function FlightDashboard() {
  const [flights, setFlights] = useState<FlightTableData[]>([]);
  const [lastUpdateTime, setLastUpdateTime] = useState(new Date());
  const [error, setError] = useState<string | null>(null);
  const [websocketUrl, setWebsocketUrl] = useState<string>('');
  const [apiGatewayUrl, setApiGatewayUrl] = useState<string>('');
  
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('disconnected');
  
  const wsRef = useRef<WebSocket | null>(null);
  const flightRemoveTimersRef = useRef<Map<string, NodeJS.Timeout>>(new Map());

  // Reconnect on refresh
  useEffect(() => {
    const savedWsUrl = sessionStorage.getItem('websocket_url');
    const savedApiUrl = sessionStorage.getItem('api_gateway_url');
    
    if (savedWsUrl && savedApiUrl) {
      console.log('🔄 Restoring connections after refresh');
      setWebsocketUrl(savedWsUrl);
      setApiGatewayUrl(savedApiUrl);
      connectWebSocket(savedWsUrl);
    }
  }, []);

  const handleWebSocketMessage = useCallback((event: MessageEvent) => {
    try {
      const message = JSON.parse(event.data);
      console.log('📨 WebSocket message received:', message.type, message.data.id);

      if (message.type === 'NEW_FLIGHT') {
        const newFlight: FlightTableData = message.data;
        
        setFlights(prev => {
          const existingFlightIndex = prev.findIndex(f => f.id === newFlight.id);
          if (existingFlightIndex !== -1) {
            console.log('⚠️ Flight already exists, duplicate prevented:', newFlight.id);
            return prev;
          }
          
          const newFlights = [newFlight, ...prev];
          if (newFlights.length > 12) {
            return newFlights.slice(0, 12);
          }
          return newFlights;
        });

        setLastUpdateTime(new Date());

      } else if (message.type === 'DELAY_PREDICTED') {
        const updatedFlight: FlightTableData = message.data;
        
        setFlights(prev => 
          prev.map(flight => {
            if (flight.id === updatedFlight.id) {
              console.log(`🕐 Delay predicted for ${flight.id}: ${updatedFlight.dep_delay} minutes`);
              
              const existingTimer = flightRemoveTimersRef.current.get(flight.id);
              if (existingTimer) {
                clearTimeout(existingTimer);
              }
              
              const removeTimer = setTimeout(() => {
                setFlights(current => {
                  const filtered = current.filter(f => f.id !== updatedFlight.id);
                  console.log(`🗑️ Flight removed: ${updatedFlight.id}, Remaining: ${filtered.length}`);
                  return filtered;
                });
                flightRemoveTimersRef.current.delete(flight.id);
              }, 3000);
              
              flightRemoveTimersRef.current.set(flight.id, removeTimer);
              
              return { ...flight, dep_delay: updatedFlight.dep_delay };
            }
            return flight;
          })
        );
        
        setLastUpdateTime(new Date());
      }
    } catch (err) {
      console.error('Error parsing WebSocket message:', err);
    }
  }, []);

  const connectWebSocket = useCallback((url: string) => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    console.log('🔗 Connecting to WebSocket:', url);
    setWebsocketUrl(url);
    setConnectionStatus('connecting');
    setError(null);
    
    sessionStorage.setItem('websocket_url', url);
    
    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('✅ WebSocket connection established');
        setConnectionStatus('connected');
        setError(null);
      };

      ws.onmessage = handleWebSocketMessage;

      ws.onclose = (event) => {
        console.log('❌ WebSocket closed:', event.code, event.reason);
        setConnectionStatus('disconnected');
      };

      ws.onerror = (error) => {
        console.error('🚨 WebSocket error:', error);
        setConnectionStatus('error');
        setError('WebSocket connection error');
      };

    } catch (err) {
      console.error('WebSocket could not be created:', err);
      setConnectionStatus('error');
      setError('Invalid WebSocket URL or connection failed');
    }
  }, [handleWebSocketMessage]);

  const handleConnect = useCallback((wsUrl: string, apiUrl: string) => {
    console.log('🎯 Connect button clicked');
    console.log('WebSocket URL:', wsUrl);
    console.log('API Gateway URL:', apiUrl);
    
    setApiGatewayUrl(apiUrl);
    sessionStorage.setItem('api_gateway_url', apiUrl);
    
    connectWebSocket(wsUrl);
  }, [connectWebSocket]);

  const handleDisconnect = useCallback(() => {
    console.log('🔌 Manual disconnect...');
    
    if (wsRef.current) {
      wsRef.current.close(1000, 'Manual disconnect');
      wsRef.current = null;
    }
    
    setConnectionStatus('disconnected');
    setWebsocketUrl('');
    setApiGatewayUrl('');
    setError(null);
    sessionStorage.removeItem('websocket_url');
    sessionStorage.removeItem('api_gateway_url');
  }, []);

  const handleReconnect = useCallback(() => {
    console.log('🔄 Manual reconnect...');
    
    if (!websocketUrl) {
      setError('No WebSocket URL to reconnect to');
      return;
    }
    
    setConnectionStatus('connecting');
    setError(null);
    connectWebSocket(websocketUrl);
  }, [websocketUrl, connectWebSocket]);

  useEffect(() => {
    return () => {
      console.log('🧹 Cleaning up...');
      
      flightRemoveTimersRef.current.forEach((timer) => clearTimeout(timer));
      flightRemoveTimersRef.current.clear();
      
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  const stats = {
    totalFlights: flights.length,
    waitingPrediction: flights.filter(f => f.dep_delay === null).length,
    predictedFlights: flights.filter(f => f.dep_delay !== null).length,
    averageDelay: flights.filter(f => f.dep_delay !== null && f.dep_delay > 0).length > 0
      ? Math.round(flights.filter(f => f.dep_delay !== null && f.dep_delay > 0)
          .reduce((acc, f) => acc + (f.dep_delay || 0), 0) / 
          flights.filter(f => f.dep_delay !== null && f.dep_delay > 0).length)
      : 0
  };

  const ConnectionStatusBadge = () => {
    const statusConfig = {
      connecting: { icon: RefreshCw, color: 'text-yellow-500', text: 'Connecting...', bg: 'bg-yellow-50 dark:bg-yellow-900/20' },
      connected: { icon: Wifi, color: 'text-green-500', text: 'Live Connected', bg: 'bg-green-50 dark:bg-green-900/20' },
      disconnected: { icon: WifiOff, color: 'text-red-500', text: 'Disconnected', bg: 'bg-red-50 dark:bg-red-900/20' },
      error: { icon: AlertTriangle, color: 'text-red-500', text: 'Connection Error', bg: 'bg-red-50 dark:bg-red-900/20' }
    };

    const config = statusConfig[connectionStatus];
    const Icon = config.icon;

    return (
      <div className={`flex items-center px-3 py-1 rounded-full ${config.bg}`}>
        <Icon size={16} className={`mr-2 ${config.color}`} />
        <span className={`text-sm font-medium ${config.color}`}>
          {config.text}
        </span>
      </div>
    );
  };

  useEffect(() => {
    if (typeof window !== 'undefined' && Notification.permission === 'default') {
      Notification.requestPermission().then(permission => {
        if (permission === 'granted') {
          console.log('🔔 Notifications enabled');
        }
      });
    }
  }, []);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white flex items-center">
                <Plane className="mr-3 text-blue-600 dark:text-blue-400" size={32} />
                Real-Time Flight Delay Prediction
              </h1>
              <p className="text-gray-600 dark:text-gray-400 mt-1">
                AWS SageMaker ML Pipeline • DynamoDB Stream • WebSocket Live
              </p>
            </div>
            <div className="flex items-center space-x-4">
              <div className="text-right">
                <div className="text-sm text-gray-500 dark:text-gray-400">Live ML Pipeline</div>
                <ConnectionStatusBadge />
                <div className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                  Last update: {lastUpdateTime.toLocaleTimeString()}
                  {connectionStatus !== 'connected' && websocketUrl && (
                    <button 
                      onClick={handleReconnect}
                      className="ml-2 text-blue-500 hover:text-blue-700 text-xs"
                    >
                      Retry
                    </button>
                  )}
                  {websocketUrl && (
                    <button 
                      onClick={handleDisconnect}
                      className="ml-2 text-red-500 hover:text-red-700 text-xs"
                    >
                      Disconnect
                    </button>
                  )}
                </div>
                {websocketUrl && (
                  <div className="text-xs text-gray-400 dark:text-gray-500 mt-1 truncate max-w-xs">
                    {websocketUrl}
                  </div>
                )}
              </div>
              <ConnectButton 
                onConnect={handleConnect}
                isConnected={connectionStatus === 'connected'}
                connectionStatus={connectionStatus}
              />
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {!websocketUrl ? (
          <div className="text-center py-20">
            <div className="max-w-md mx-auto">
              <WifiOff className="mx-auto mb-6 text-gray-400" size={64} />
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
                WebSocket Connection Required
              </h2>
              <p className="text-gray-600 dark:text-gray-400 mb-6">
                Please connect to a WebSocket server to start receiving real-time flight data.
              </p>
              <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4 text-sm text-gray-700 dark:text-gray-300">
                <p className="font-medium mb-2">Expected URL format:</p>
                <code className="bg-black/10 dark:bg-white/10 px-2 py-1 rounded">
                  wss://&lt;id&gt;.execute-api.&lt;region&gt;.amazonaws.com/prod/
                </code>
              </div>
            </div>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
                <div className="flex items-center">
                  <Plane className="text-blue-500" size={24} />
                  <div className="ml-4">
                    <p className="text-2xl font-semibold text-gray-900 dark:text-white">{stats.totalFlights}/12</p>
                    <p className="text-gray-600 dark:text-gray-400 text-sm">Active Flights</p>
                  </div>
                </div>
              </div>

              <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
                <div className="flex items-center">
                  <Clock className="text-yellow-500" size={24} />
                  <div className="ml-4">
                    <p className="text-2xl font-semibold text-gray-900 dark:text-white">{stats.waitingPrediction}</p>
                    <p className="text-gray-600 dark:text-gray-400 text-sm">Ready for Departure</p>
                  </div>
                </div>
              </div>

              <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
                <div className="flex items-center">
                  <Activity className="text-green-500" size={24} />
                  <div className="ml-4">
                    <p className="text-2xl font-semibold text-gray-900 dark:text-white">{stats.predictedFlights}</p>
                    <p className="text-gray-600 dark:text-gray-400 text-sm">Departed</p>
                  </div>
                </div>
              </div>

              <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
                <div className="flex items-center">
                  <AlertTriangle className="text-red-500" size={24} />
                  <div className="ml-4">
                    <p className="text-2xl font-semibold text-gray-900 dark:text-white">{stats.averageDelay}min</p>
                    <p className="text-gray-600 dark:text-gray-400 text-sm">Avg. Delay</p>
                  </div>
                </div>
              </div>
            </div>

            <FlightGrid data={flights} />
            
            {flights.length === 0 && connectionStatus === 'connected' && (
              <div className="text-center py-12 text-gray-500 dark:text-gray-400">
                <Plane className="mx-auto mb-4" size={48} />
                📡 Waiting for flight data from DynamoDB streams...
                <div className="text-sm mt-2">Ensure your EC2 instance is running and sending data</div>
              </div>
            )}

            {connectionStatus === 'connecting' && (
              <div className="text-center py-12">
                <RefreshCw className="mx-auto mb-4 animate-spin text-blue-500" size={48} />
                <div className="text-gray-500 dark:text-gray-400">Connecting to AWS WebSocket...</div>
              </div>
            )}

            {error && (
              <div className="text-center py-6">
                <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
                  <AlertTriangle className="mx-auto text-red-500 mb-2" size={24} />
                  <p className="text-red-700 dark:text-red-300">{error}</p>
                  <div className="space-x-2 mt-2">
                    <button 
                      onClick={handleReconnect}
                      className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors text-sm"
                    >
                      Retry
                    </button>
                    <button 
                      onClick={handleDisconnect}
                      className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors text-sm"
                    >
                      Change URL
                    </button>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      <Chatbot />
    </div>
  );
}