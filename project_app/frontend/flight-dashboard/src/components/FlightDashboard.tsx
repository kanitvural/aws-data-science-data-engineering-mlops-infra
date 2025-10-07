// components/FlightDashboard.tsx
"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import FlightGrid from "@/components/FlightGrid";
import Chatbot from "@/components/Chatbot";
import { FlightTableData } from "@/types/flight";
import {
  Plane,
  Activity,
  Clock,
  AlertTriangle,
  Wifi,
  WifiOff,
  RefreshCw,
} from "lucide-react";
import LogoutButton from "./LogoutButton";

export default function FlightDashboard() {
  const [flights, setFlights] = useState<FlightTableData[]>([]);
  const [lastUpdateTime, setLastUpdateTime] = useState(new Date());
  const [error, setError] = useState<string | null>(null);

  const [connectionStatus, setConnectionStatus] = useState<
    "connecting" | "connected" | "disconnected" | "error"
  >("disconnected");

  const wsRef = useRef<WebSocket | null>(null);
  const flightRemoveTimersRef = useRef<Map<string, NodeJS.Timeout>>(new Map());

  // Read URLs from environment variables
  const websocketUrl = process.env.NEXT_PUBLIC_WEBSOCKET_URL || "";
  const apiGatewayChatbotUrl = process.env.NEXT_PUBLIC_APIGATEWAY_CHATBOT_URL || "";
  const apiGatewayAuthUrl = process.env.NEXT_PUBLIC_API_GATEWAY_AUTH_URL || "";

  // Get User Name
  const [userName, setUserName] = useState<string | null>(null);
  useEffect(() => {
    const name = sessionStorage.getItem("userFirstName");
    if (name) setUserName(name);
  }, []);

  // Auto-connect on component mount
  useEffect(() => {
    if (websocketUrl) {
      console.log("🚀 Auto-connecting to WebSocket from environment variables");
      connectWebSocket(websocketUrl);
    } else {
      console.error("❌ NEXT_PUBLIC_WEBSOCKET_URL is not defined in .env.local");
    }
  }, []);

  const handleWebSocketMessage = useCallback((event: MessageEvent) => {
    try {
      const message = JSON.parse(event.data);
      console.log(
        "📨 WebSocket message received:",
        message.type,
        message.data.id
      );

      if (message.type === "NEW_FLIGHT") {
        const newFlight: FlightTableData = message.data;

        setFlights((prev) => {
          const existingFlightIndex = prev.findIndex(
            (f) => f.id === newFlight.id
          );
          if (existingFlightIndex !== -1) {
            console.log(
              "⚠️ Flight already exists, duplicate prevented:",
              newFlight.id
            );
            return prev;
          }

          const newFlights = [newFlight, ...prev];
          if (newFlights.length > 12) {
            return newFlights.slice(0, 12);
          }
          return newFlights;
        });

        setLastUpdateTime(new Date());
      } else if (message.type === "DELAY_PREDICTED") {
        const updatedFlight: FlightTableData = message.data;

        setFlights((prev) =>
          prev.map((flight) => {
            if (flight.id === updatedFlight.id) {
              console.log(
                `🕐 Delay predicted for ${flight.id}: ${updatedFlight.dep_delay} minutes`
              );

              const existingTimer = flightRemoveTimersRef.current.get(
                flight.id
              );
              if (existingTimer) {
                clearTimeout(existingTimer);
              }

              const removeTimer = setTimeout(() => {
                setFlights((current) => {
                  const filtered = current.filter(
                    (f) => f.id !== updatedFlight.id
                  );
                  console.log(
                    `🗑️ Flight removed: ${updatedFlight.id}, Remaining: ${filtered.length}`
                  );
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
      console.error("Error parsing WebSocket message:", err);
    }
  }, []);

  const connectWebSocket = useCallback(
    (url: string) => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }

      console.log("🔗 Connecting to WebSocket:", url);
      setConnectionStatus("connecting");
      setError(null);

      try {
        const ws = new WebSocket(url);
        wsRef.current = ws;

        ws.onopen = () => {
          console.log("✅ WebSocket connection established");
          setConnectionStatus("connected");
          setError(null);
        };

        ws.onmessage = handleWebSocketMessage;

        ws.onclose = (event) => {
          console.log("❌ WebSocket closed:", event.code, event.reason);
          setConnectionStatus("disconnected");
        };

        ws.onerror = (error) => {
          console.error("🚨 WebSocket error:", error);
          setConnectionStatus("error");
          setError("WebSocket connection error");
        };
      } catch (err) {
        console.error("WebSocket could not be created:", err);
        setConnectionStatus("error");
        setError("Invalid WebSocket URL or connection failed");
      }
    },
    [handleWebSocketMessage]
  );

  const handleReconnect = useCallback(() => {
    console.log("🔄 Manual reconnect...");

    if (!websocketUrl) {
      setError("NEXT_PUBLIC_WEBSOCKET_URL is not defined");
      return;
    }

    setConnectionStatus("connecting");
    setError(null);
    connectWebSocket(websocketUrl);
  }, [websocketUrl, connectWebSocket]);

  const handleDisconnect = useCallback(() => {
    console.log("🔌 Manual disconnect...");

    if (wsRef.current) {
      wsRef.current.close(1000, "Manual disconnect");
      wsRef.current = null;
    }

    setConnectionStatus("disconnected");
    setError(null);
  }, []);

  useEffect(() => {
    return () => {
      console.log("🧹 Cleaning up...");

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
    waitingPrediction: flights.filter((f) => f.dep_delay === null).length,
    predictedFlights: flights.filter((f) => f.dep_delay !== null).length,
    averageDelay:
      flights.filter((f) => f.dep_delay !== null && f.dep_delay > 0).length > 0
        ? Math.round(
            flights
              .filter((f) => f.dep_delay !== null && f.dep_delay > 0)
              .reduce((acc, f) => acc + (f.dep_delay || 0), 0) /
              flights.filter((f) => f.dep_delay !== null && f.dep_delay > 0)
                .length
          )
        : 0,
  };

  const ConnectionStatusBadge = () => {
    const statusConfig = {
      connecting: {
        icon: RefreshCw,
        color: "text-yellow-500",
        text: "Connecting...",
        bg: "bg-yellow-50 dark:bg-yellow-900/20",
      },
      connected: {
        icon: Wifi,
        color: "text-green-500",
        text: "Live Connected",
        bg: "bg-green-50 dark:bg-green-900/20",
      },
      disconnected: {
        icon: WifiOff,
        color: "text-red-500",
        text: "Disconnected",
        bg: "bg-red-50 dark:bg-red-900/20",
      },
      error: {
        icon: AlertTriangle,
        color: "text-red-500",
        text: "Connection Error",
        bg: "bg-red-50 dark:bg-red-900/20",
      },
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
    if (
      typeof window !== "undefined" &&
      Notification.permission === "default"
    ) {
      Notification.requestPermission().then((permission) => {
        if (permission === "granted") {
          console.log("🔔 Notifications enabled");
        }
      });
    }
  }, []);

  // Environment configuration check
  if (!websocketUrl && !apiGatewayChatbotUrl && !apiGatewayAuthUrl) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
        <div className="max-w-md mx-auto text-center p-8">
          <AlertTriangle className="mx-auto mb-6 text-red-500" size={64} />
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
            Environment Configuration Error
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mb-6">
            Required environment variables are not defined in .env.local
          </p>
          <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-4 text-sm text-left">
            <p className="font-medium mb-2 text-gray-900 dark:text-white">
              Please add these variables to .env.local:
            </p>
            <code className="block bg-black/10 dark:bg-white/10 px-3 py-2 rounded text-xs">
              NEXT_PUBLIC_WEBSOCKET_URL=wss://...
              <br />
              NEXT_PUBLIC_APIGATEWAY_CHATBOT_URL=https://...
              <br />
              NEXT_PUBLIC_API_GATEWAY_AUTH_URL=https://...
            </code>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white flex items-center">
                <Plane
                  className="mr-3 text-blue-600 dark:text-blue-400"
                  size={32}
                />
                Real-Time Flight Delay Prediction
              </h1>
              <p className="text-gray-600 dark:text-gray-400 mt-1">
                Ultimate AWS AI Project ✈️ Data Engineering • Data Science • MLOps • LLM • Real-Time Web App
              </p>
            </div>
            <div className="flex items-center gap-6">
              {/* Connection Status Section */}
              <div className="flex flex-col items-center text-center">
                <div className="text-sm text-gray-500 dark:text-gray-400 mb-2">
                  Live ML Prediction
                </div>
                <ConnectionStatusBadge />
                <div className="text-xs text-gray-400 dark:text-gray-500 mt-2 space-x-2">
                  <span>Last update: {lastUpdateTime.toLocaleTimeString()}</span>
                  {connectionStatus !== "connected" && (
                    <button
                      onClick={handleReconnect}
                      className="text-blue-500 hover:text-blue-700 font-medium transition-colors"
                    >
                      Retry
                    </button>
                  )}
                  {connectionStatus === "connected" && (
                    <button
                      onClick={handleDisconnect}
                      className="text-red-500 hover:text-red-700 font-medium transition-colors"
                    >
                      Disconnect
                    </button>
                  )}
                </div>
                {websocketUrl && (
                  <div className="text-xs text-gray-400 dark:text-gray-500 mt-1 truncate max-w-xs">
                    {websocketUrl.substring(0, 40)}...
                  </div>
                )}
              </div>

              {/* User Profile Section */}
              {userName && (
                <div className="flex items-center gap-3 px-4 py-2 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 rounded-xl border border-blue-200 dark:border-blue-800">
                  <div className="flex items-center justify-center w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 text-white font-bold text-sm shadow-lg">
                    {userName.charAt(0).toUpperCase()}
                  </div>
                  <div className="text-left">
                    <div className="text-xs text-gray-500 dark:text-gray-400">Welcome back</div>
                    <div className="text-sm font-semibold text-gray-900 dark:text-white">
                      {userName}
                    </div>
                  </div>
                </div>
              )}

              <LogoutButton />
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
            <div className="flex items-center">
              <Plane className="text-blue-500" size={24} />
              <div className="ml-4">
                <p className="text-2xl font-semibold text-gray-900 dark:text-white">
                  {stats.totalFlights}/12
                </p>
                <p className="text-gray-600 dark:text-gray-400 text-sm">
                  Active Flights
                </p>
              </div>
            </div>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
            <div className="flex items-center">
              <Clock className="text-yellow-500" size={24} />
              <div className="ml-4">
                <p className="text-2xl font-semibold text-gray-900 dark:text-white">
                  {stats.waitingPrediction}
                </p>
                <p className="text-gray-600 dark:text-gray-400 text-sm">
                  Ready for Departure
                </p>
              </div>
            </div>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
            <div className="flex items-center">
              <Activity className="text-green-500" size={24} />
              <div className="ml-4">
                <p className="text-2xl font-semibold text-gray-900 dark:text-white">
                  {stats.predictedFlights}
                </p>
                <p className="text-gray-600 dark:text-gray-400 text-sm">
                  Departed
                </p>
              </div>
            </div>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
            <div className="flex items-center">
              <AlertTriangle className="text-red-500" size={24} />
              <div className="ml-4">
                <p className="text-2xl font-semibold text-gray-900 dark:text-white">
                  {stats.averageDelay}min
                </p>
                <p className="text-gray-600 dark:text-gray-400 text-sm">
                  Avg. Delay
                </p>
              </div>
            </div>
          </div>
        </div>

        <FlightGrid data={flights} />

        {flights.length === 0 && connectionStatus === "connected" && (
          <div className="text-center py-12 text-gray-500 dark:text-gray-400">
            <Plane className="mx-auto mb-4" size={48} />
            📡 Waiting for flight data from DynamoDB streams...
            <div className="text-sm mt-2">
              Ensure your EC2 instance is running and sending data
            </div>
          </div>
        )}

        {connectionStatus === "connecting" && (
          <div className="text-center py-12">
            <RefreshCw
              className="mx-auto mb-4 animate-spin text-blue-500"
              size={48}
            />
            <div className="text-gray-500 dark:text-gray-400">
              Connecting to AWS WebSocket...
            </div>
          </div>
        )}

        {error && (
          <div className="text-center py-6">
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
              <AlertTriangle
                className="mx-auto text-red-500 mb-2"
                size={24}
              />
              <p className="text-red-700 dark:text-red-300">{error}</p>
              <div className="space-x-2 mt-2">
                <button
                  onClick={handleReconnect}
                  className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors text-sm"
                >
                  Retry Connection
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      <Chatbot />
    </div>
  );
}