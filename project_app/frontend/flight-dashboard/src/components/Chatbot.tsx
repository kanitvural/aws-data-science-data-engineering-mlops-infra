"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MessageCircle, X, Send, Bot } from "lucide-react";

// UUID v4 generator
function generateUUID(): string {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export default function Chatbot() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<
    Array<{ text: string; isUser: boolean; id: string }>
  >([]);
  const [inputValue, setInputValue] = useState("");
  const [sessionId, setSessionId] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Initialize or retrieve sessionId from sessionStorage
  useEffect(() => {
    let storedSessionId = sessionStorage.getItem("chatbot_session_id");
    if (!storedSessionId) {
      // Use the same session ID as in your Python code
      storedSessionId = generateUUID();
      sessionStorage.setItem("chatbot_session_id", storedSessionId);
      console.log("🆔 Session ID set to:", storedSessionId);
    } else {
      console.log("🆔 Session ID retrieved from storage:", storedSessionId);
    }
    setSessionId(storedSessionId);
  }, []);

  // Fetch history when chatbot opens and conditions are met
  useEffect(() => {
    const apiGatewayUrl = sessionStorage.getItem("api_gateway_url");
    
    if (isOpen && sessionId && apiGatewayUrl && !historyLoaded) {
      console.log("🔄 Chatbot opened, fetching history...");
      fetchHistory();
    }
  }, [isOpen, sessionId, historyLoaded]);

  // Fetch chat history from /history endpoint
  const fetchHistory = async () => {
    const apiGatewayUrl = sessionStorage.getItem("api_gateway_url");
    
    if (!apiGatewayUrl || !sessionId) {
      console.log("⏭️ Skipping history fetch - no API Gateway URL or session ID");
      return;
    }

    try {
      console.log("📥 Fetching chat history...");
      const response = await fetch(
        `${apiGatewayUrl}/history?sessionId=${sessionId}`,
        {
          method: "GET",
          headers: { "Content-Type": "application/json" },
        }
      );

      if (!response.ok) {
        throw new Error(`History fetch failed: ${response.status}`);
      }

      const data = await response.json();
      console.log("📜 History loaded:", data.count, "messages");

      // Convert history to message format
      if (data.history && data.history.length > 0) {
        const loadedMessages = data.history.map((item: any) => ({
          id: item.eventId,
          text: item.content,
          isUser: item.role.toLowerCase() === "user",
        }));

        setMessages(loadedMessages);
      }

      setHistoryLoaded(true);
    } catch (error) {
      console.error("❌ Error fetching history:", error);
      setHistoryLoaded(true); // Mark as loaded to prevent retry loops
    }
  };

  // Mesajlar değiştiğinde en alta scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleSend = async () => {
    if (!inputValue.trim()) return;

    const userMessage = {
      id: Date.now().toString() + "_user",
      text: inputValue,
      isUser: true,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue("");

    const apiGatewayUrl = sessionStorage.getItem("api_gateway_url");

    if (!apiGatewayUrl) {
      setTimeout(() => {
        const botMessage = {
          id: Date.now().toString() + "_bot",
          text: "API Gateway is not connected. Please connect to the API Gateway URL first using the Connect button.",
          isUser: false,
        };
        setMessages((prev) => [...prev, botMessage]);
      }, 500);
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch(`${apiGatewayUrl}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: userMessage.text,
          sessionId: sessionId,
        }),
      });

      if (!response.ok)
        throw new Error(`API request failed: ${response.status}`);

      const data = await response.json();
      const botMessage = {
        id: Date.now().toString() + "_bot",
        text: data.response || "Response received from AWS Bedrock.",
        isUser: false,
      };

      setMessages((prev) => [...prev, botMessage]);
    } catch (error) {
      console.error("Error calling API Gateway:", error);
      const errorMessage = {
        id: Date.now().toString() + "_bot",
        text: `Error connecting to API Gateway. Please check your connection. (Session: ${sessionId.substring(
          0,
          8
        )}...)`,
        isUser: false,
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-50">
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 100, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 100, scale: 0.95 }}
            transition={{
              type: "spring",
              damping: 25,
              stiffness: 300,
              duration: 0.3,
            }}
            className="absolute bottom-20 right-0 w-[420px] h-[650px] bg-white dark:bg-gray-800 rounded-lg shadow-2xl border border-gray-200 dark:border-gray-700 flex flex-col"
            style={{ transformOrigin: "bottom right" }}
          >
            {/* Header */}
            <div className="flex items-center justify-between p-5 bg-gradient-to-r from-blue-600 to-blue-700 dark:from-blue-700 dark:to-blue-800 text-white rounded-t-lg">
              <div className="flex items-center space-x-2">
                <Bot size={22} />
                <h3 className="font-semibold text-lg">Flight Assistant</h3>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="hover:bg-blue-500 dark:hover:bg-blue-600 rounded-full p-2 transition-colors"
              >
                <X size={20} />
              </button>
            </div>

            {/* Messages */}
            <div
              className="flex-1 p-5 space-y-4 text-base"
              style={{
                overflowY: "scroll",
                scrollbarWidth: "none",
                msOverflowStyle: "none",
              }}
            >
              <style jsx>{`
                div::-webkit-scrollbar {
                  display: none;
                }
              `}</style>

              {messages.length === 0 && (
                <div className="text-center text-gray-500 dark:text-gray-400">
                  <Bot
                    className="mx-auto mb-3 text-gray-400 dark:text-gray-500"
                    size={36}
                  />
                  <p>Hi! I&apos;m your flight data assistant.</p>
                  <p className="text-sm mt-1">
                    Ask me about flight patterns, delays, or weather impacts!
                  </p>
                  {sessionId && (
                    <p className="text-xs mt-2 text-gray-400">
                      Session: {sessionId.substring(0, 8)}...
                    </p>
                  )}
                </div>
              )}

              {messages.map((message) => (
                <motion.div
                  key={message.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`flex ${
                    message.isUser ? "justify-end" : "justify-start"
                  }`}
                >
                  <div
                    className={`max-w-[85%] p-4 rounded-lg text-base ${
                      message.isUser
                        ? "bg-blue-600 text-white rounded-br-none"
                        : "bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200 rounded-bl-none"
                    }`}
                  >
                    {message.text}
                  </div>
                </motion.div>
              ))}

              {isLoading && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex justify-start"
                >
                  <div className="bg-gray-100 dark:bg-gray-700 p-4 rounded-lg rounded-bl-none">
                    <div className="flex space-x-2">
                      <div
                        className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                        style={{ animationDelay: "0ms" }}
                      ></div>
                      <div
                        className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                        style={{ animationDelay: "150ms" }}
                      ></div>
                      <div
                        className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                        style={{ animationDelay: "300ms" }}
                      ></div>
                    </div>
                  </div>
                </motion.div>
              )}

              {/* Scroll helper div */}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="p-5 border-t border-gray-200 dark:border-gray-700">
              <div className="flex items-center space-x-3">
                <input
                  type="text"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask about flight data..."
                  disabled={isLoading}
                  className="flex-1 px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg text-base bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed"
                />
                <button
                  onClick={handleSend}
                  disabled={!inputValue.trim() || isLoading}
                  className="bg-blue-600 hover:bg-blue-700 text-white p-3 rounded-lg disabled:bg-gray-300 dark:disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors"
                >
                  <Send size={18} />
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Toggle Button */}
      <motion.button
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onClick={() => setIsOpen(!isOpen)}
        className="bg-blue-600 hover:bg-blue-700 dark:bg-blue-700 dark:hover:bg-blue-800 text-white rounded-full p-5 shadow-lg transition-colors"
      >
        <AnimatePresence mode="wait">
          {isOpen ? (
            <motion.div
              key="close"
              initial={{ rotate: -90, opacity: 0 }}
              animate={{ rotate: 0, opacity: 1 }}
              exit={{ rotate: 90, opacity: 0 }}
              transition={{ duration: 0.2 }}
            >
              <X size={24} />
            </motion.div>
          ) : (
            <motion.div
              key="open"
              initial={{ rotate: 90, opacity: 0 }}
              animate={{ rotate: 0, opacity: 1 }}
              exit={{ rotate: -90, opacity: 0 }}
              transition={{ duration: 0.2 }}
            >
              <MessageCircle size={24} />
            </motion.div>
          )}
        </AnimatePresence>
      </motion.button>
    </div>
  );
}