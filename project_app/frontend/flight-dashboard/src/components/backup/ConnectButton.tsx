import React, { useState, useEffect } from 'react';
import { Zap, X, Wifi, WifiOff, ExternalLink, Globe } from 'lucide-react';

export default function ConnectButton({ 
  onConnect, 
  isConnected = false, 
  connectionStatus = 'disconnected' 
}: { 
  onConnect?: (websocketUrl: string, apiGatewayUrl: string, apiGatewayAuthUrl: string) => void;
  isConnected?: boolean;
  connectionStatus?: 'connecting' | 'connected' | 'disconnected' | 'error';
}) {
  const [mounted, setMounted] = useState(false);
  const [showModal, setShowModal] = useState(false);

  // URLs
  const [websocketUrl, setWebsocketUrl] = useState('');
  const [apiGatewayUrl, setApiGatewayUrl] = useState('');
  const [apiGatewayAuthUrl, setApiGatewayAuthUrl] = useState('');

  // Validations
  const [isValidWebsocketUrl, setIsValidWebsocketUrl] = useState(false);
  const [isValidApiGatewayUrl, setIsValidApiGatewayUrl] = useState(false);
  const [isValidApiGatewayAuthUrl, setIsValidApiGatewayAuthUrl] = useState(false);

  // Input focus
  const [wsInputFocused, setWsInputFocused] = useState(false);
  const [apiInputFocused, setApiInputFocused] = useState(false);
  const [apiAuthInputFocused, setApiAuthInputFocused] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  // WebSocket URL validation
  useEffect(() => {
    const wsRegex = /^wss?:\/\/.+/;
    setIsValidWebsocketUrl(websocketUrl.length > 0 && wsRegex.test(websocketUrl));
  }, [websocketUrl]);

  // API Gateway URL validation
  useEffect(() => {
    const apiRegex = /^https?:\/\/.+/;
    setIsValidApiGatewayUrl(apiGatewayUrl.length > 0 && apiRegex.test(apiGatewayUrl));
  }, [apiGatewayUrl]);

  // API Gateway Auth URL validation
  useEffect(() => {
    const apiRegex = /^https?:\/\/.+/;
    setIsValidApiGatewayAuthUrl(apiGatewayAuthUrl.length > 0 && apiRegex.test(apiGatewayAuthUrl));
  }, [apiGatewayAuthUrl]);

  const handleConnect = () => {
    if (isValidWebsocketUrl || isValidApiGatewayUrl || isValidApiGatewayAuthUrl) {
      onConnect?.(websocketUrl, apiGatewayUrl, apiGatewayAuthUrl);
      setShowModal(false);
      setWebsocketUrl('');
      setApiGatewayUrl('');
      setApiGatewayAuthUrl('');
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (isValidWebsocketUrl || isValidApiGatewayUrl || isValidApiGatewayAuthUrl)) {
      handleConnect();
    }
    if (e.key === 'Escape') {
      setShowModal(false);
    }
  };

  if (!mounted) return null;

  const getButtonIcon = () => {
    switch (connectionStatus) {
      case 'connected': return <Wifi className="h-5 w-5" />;
      case 'connecting': return <Zap className="h-5 w-5 animate-pulse" />;
      case 'error': return <WifiOff className="h-5 w-5" />;
      default: return <Globe className="h-5 w-5" />;
    }
  };

  const getButtonStyles = () => {
    const base = "relative inline-flex h-12 w-12 items-center justify-center rounded-full transition-all duration-300 shadow-lg hover:shadow-xl transform hover:scale-105 focus:outline-none focus:ring-2 focus:ring-offset-2";
    switch (connectionStatus) {
      case 'connected': return `${base} bg-gradient-to-r from-green-400 to-green-600 text-white hover:from-green-500 hover:to-green-700 focus:ring-green-500`;
      case 'connecting': return `${base} bg-gradient-to-r from-yellow-400 to-orange-500 text-white hover:from-yellow-500 hover:to-orange-600 focus:ring-yellow-500`;
      case 'error': return `${base} bg-gradient-to-r from-red-400 to-red-600 text-white hover:from-red-500 hover:to-red-700 focus:ring-red-500`;
      default: return `${base} bg-gradient-to-r from-blue-500 to-indigo-600 text-white hover:from-blue-600 hover:to-indigo-700 focus:ring-blue-500`;
    }
  };

  return (
    <>
      <div className="relative">
        <button onClick={() => setShowModal(true)} className={getButtonStyles()} aria-label="Connect to WebSocket">
          {getButtonIcon()}
          {connectionStatus === 'connected' && (
            <div className="absolute -top-1 -right-1 h-4 w-4 bg-green-500 rounded-full animate-pulse border-2 border-white"></div>
          )}
          {connectionStatus === 'error' && (
            <div className="absolute -top-1 -right-1 h-4 w-4 bg-red-500 rounded-full border-2 border-white"></div>
          )}
        </button>
      </div>

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity duration-300" onClick={() => setShowModal(false)} />
          <div className="relative bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-md transform transition-all duration-300 scale-100">
            <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
              <div className="flex items-center space-x-3">
                <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-full">
                  <Globe className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Connect Services</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Enter WebSocket and API Gateway URLs</p>
                </div>
              </div>
              <button onClick={() => setShowModal(false)} className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-full transition-colors">
                <X className="h-5 w-5 text-gray-500" />
              </button>
            </div>

            {/* Body */}
            <div className="p-6 space-y-4">

              {/* WebSocket URL */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">WebSocket URL</label>
                <div className="relative">
                  <input
                    type="text"
                    className={`w-full px-4 py-3 rounded-xl border-2 transition-all duration-200 focus:outline-none ${
                      wsInputFocused || websocketUrl 
                        ? isValidWebsocketUrl 
                          ? 'border-green-400 focus:border-green-500 bg-green-50/30 dark:bg-green-900/10' 
                          : websocketUrl.length > 0 
                            ? 'border-red-400 focus:border-red-500 bg-red-50/30 dark:bg-red-900/10'
                            : 'border-blue-400 focus:border-blue-500 bg-blue-50/30 dark:bg-blue-900/10'
                        : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'
                    } dark:bg-gray-700 dark:text-white placeholder-gray-500 dark:placeholder-gray-400`}
                    placeholder="wss://<id>.execute-api.<region>.amazonaws.com/prod/"
                    value={websocketUrl}
                    onChange={(e) => setWebsocketUrl(e.target.value)}
                    onFocus={() => setWsInputFocused(true)}
                    onBlur={() => setWsInputFocused(false)}
                    onKeyDown={handleKeyPress}
                    autoFocus
                  />
                  {websocketUrl && (
                    <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
                      <div className={`h-2 w-2 rounded-full ${isValidWebsocketUrl ? 'bg-green-500' : 'bg-red-500'}`}></div>
                    </div>
                  )}
                </div>
                {websocketUrl && !isValidWebsocketUrl && (
                  <p className="mt-2 text-sm text-red-600 dark:text-red-400 flex items-center">
                    <ExternalLink className="h-4 w-4 mr-1" />
                    Please enter a valid WebSocket URL (ws:// or wss://)
                  </p>
                )}
              </div>

              {/* API Gateway URL */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">API Gateway URL</label>
                <div className="relative">
                  <input
                    type="text"
                    className={`w-full px-4 py-3 rounded-xl border-2 transition-all duration-200 focus:outline-none ${
                      apiInputFocused || apiGatewayUrl
                        ? isValidApiGatewayUrl 
                          ? 'border-green-400 focus:border-green-500 bg-green-50/30 dark:bg-green-900/10'
                          : apiGatewayUrl.length > 0
                            ? 'border-red-400 focus:border-red-500 bg-red-50/30 dark:bg-red-900/10'
                            : 'border-blue-400 focus:border-blue-500 bg-blue-50/30 dark:bg-blue-900/10'
                        : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'
                    } dark:bg-gray-700 dark:text-white placeholder-gray-500 dark:placeholder-gray-400`}
                    placeholder="https://<id>.execute-api.<region>.amazonaws.com/prod"
                    value={apiGatewayUrl}
                    onChange={(e) => setApiGatewayUrl(e.target.value)}
                    onFocus={() => setApiInputFocused(true)}
                    onBlur={() => setApiInputFocused(false)}
                    onKeyDown={handleKeyPress}
                  />
                  {apiGatewayUrl && (
                    <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
                      <div className={`h-2 w-2 rounded-full ${isValidApiGatewayUrl ? 'bg-green-500' : 'bg-red-500'}`}></div>
                    </div>
                  )}
                </div>
                {apiGatewayUrl && !isValidApiGatewayUrl && (
                  <p className="mt-2 text-sm text-red-600 dark:text-red-400 flex items-center">
                    <ExternalLink className="h-4 w-4 mr-1" />
                    Please enter a valid API Gateway URL (https://)
                  </p>
                )}
              </div>

              {/* API Gateway Auth URL */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">API Gateway Auth URL</label>
                <div className="relative">
                  <input
                    type="text"
                    className={`w-full px-4 py-3 rounded-xl border-2 transition-all duration-200 focus:outline-none ${
                      apiAuthInputFocused || apiGatewayAuthUrl
                        ? isValidApiGatewayAuthUrl 
                          ? 'border-green-400 focus:border-green-500 bg-green-50/30 dark:bg-green-900/10'
                          : apiGatewayAuthUrl.length > 0
                            ? 'border-red-400 focus:border-red-500 bg-red-50/30 dark:bg-red-900/10'
                            : 'border-blue-400 focus:border-blue-500 bg-blue-50/30 dark:bg-blue-900/10'
                        : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'
                    } dark:bg-gray-700 dark:text-white placeholder-gray-500 dark:placeholder-gray-400`}
                    placeholder="https://<id>.execute-api.<region>.amazonaws.com/auth"
                    value={apiGatewayAuthUrl}
                    onChange={(e) => setApiGatewayAuthUrl(e.target.value)}
                    onFocus={() => setApiAuthInputFocused(true)}
                    onBlur={() => setApiAuthInputFocused(false)}
                    onKeyDown={handleKeyPress}
                  />
                  {apiGatewayAuthUrl && (
                    <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
                      <div className={`h-2 w-2 rounded-full ${isValidApiGatewayAuthUrl ? 'bg-green-500' : 'bg-red-500'}`}></div>
                    </div>
                  )}
                </div>
                {apiGatewayAuthUrl && !isValidApiGatewayAuthUrl && (
                  <p className="mt-2 text-sm text-red-600 dark:text-red-400 flex items-center">
                    <ExternalLink className="h-4 w-4 mr-1" />
                    Please enter a valid API Gateway Auth URL (https://)
                  </p>
                )}
              </div>

            </div>

            {/* Footer */}
            <div className="flex items-center justify-between p-6 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700/50 rounded-b-2xl">
              <button onClick={() => setShowModal(false)} className="px-6 py-2.5 text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white transition-colors">
                Cancel
              </button>
              <button
                onClick={handleConnect}
                disabled={!isValidWebsocketUrl && !isValidApiGatewayUrl && !isValidApiGatewayAuthUrl}
                className={`px-6 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 ${
                  isValidWebsocketUrl || isValidApiGatewayUrl || isValidApiGatewayAuthUrl
                    ? 'bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-600 hover:to-indigo-700 text-white shadow-lg hover:shadow-xl transform hover:scale-105'
                    : 'bg-gray-300 dark:bg-gray-600 text-gray-500 dark:text-gray-400 cursor-not-allowed'
                }`}
              >
                <span className="flex items-center space-x-2">
                  <Zap className="h-4 w-4" />
                  <span>Connect</span>
                </span>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
