// src/contexts/AuthContext.tsx
"use client";

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
} from "react";
import { useRouter } from "next/navigation";
import {
  RestApiService,
  type LoginData,
  type SignupData,
  type ConfirmData,
  type ChatResponse,
  type HistoryResponse,
} from "@/services/restApiService";

interface User {
  username: string;
  email: string;
  firstName?: string;
  lastName?: string;
}

interface AuthContextType {
  // State
  isAuthenticated: boolean;
  isLoading: boolean;
  user: User | null;

  // Auth Methods
  login: (data: LoginData) => Promise<void>;
  logout: () => Promise<void>;
  signup: (data: SignupData) => Promise<void>;
  confirmSignup: (data: ConfirmData) => Promise<void>;
  forgotPassword: (username: string) => Promise<void>;
  confirmForgotPassword: (data: {
    username: string;
    code: string;
    newPassword: string;
  }) => Promise<void>;
  resendConfirmation: (username: string) => Promise<void>;
  checkAuth: () => Promise<boolean>;

  // Chat Methods
  sendChatMessage: (prompt: string, sessionId: string) => Promise<ChatResponse>;
  getChatHistory: (sessionId: string) => Promise<HistoryResponse>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Token refresh intervals
const FIRST_REFRESH_DELAY = 45 * 60 * 1000; // 45 minutes
const REFRESH_INTERVAL = 50 * 60 * 1000; // 50 minutes

// Token refresh intervals for test
// const FIRST_REFRESH_DELAY = 10 * 1000; // 10 second (TEST)
// const REFRESH_INTERVAL = 15 * 1000; // 15 second (TEST)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);
  const router = useRouter();
  const refreshTimerRef = useRef<NodeJS.Timeout | null>(null);

  // ==================== REFRESH TOKEN ====================
  const refreshToken = useCallback(async (): Promise<boolean> => {
    try {
      console.log("🔄 Refreshing access token...");
      await RestApiService.refreshToken();
      console.log("✅ Token refreshed successfully");
      return true;
    } catch (error) {
      console.error("❌ Token refresh failed:", error);
      // Don't call logout here - avoid circular dependency
      // refreshAndRetry in service will handle redirect
      return false;
    }
  }, []); // ← No dependencies!

  // ==================== REFRESH TIMER ====================
  const startRefreshTimer = useCallback(() => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
      clearInterval(refreshTimerRef.current);
    }

    console.log("⏰ Scheduling first token refresh in 45 minutes");

    refreshTimerRef.current = setTimeout(async () => {
      const success = await refreshToken();

      if (success) {
        console.log("⏰ Scheduling subsequent refreshes every 50 minutes");
        refreshTimerRef.current = setInterval(() => {
          refreshToken();
        }, REFRESH_INTERVAL);
      }
    }, FIRST_REFRESH_DELAY);
  }, [refreshToken]);

  const stopRefreshTimer = useCallback(() => {
    if (refreshTimerRef.current) {
      console.log("⏹️ Stopping token refresh timer");
      clearTimeout(refreshTimerRef.current);
      clearInterval(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }
  }, []);

  // ==================== CHECK AUTH ====================
  const checkAuth = useCallback(async (): Promise<boolean> => {
    try {
      const result = await RestApiService.getCurrentUser();

      // Check for error
      if (result.error) {
        console.log("ℹ️ Not authenticated");
        setUser(null);
        setIsAuthenticated(false);
        return false;
      }

      type CognitoAttr = { Name: string; Value?: string };
      const attrs: CognitoAttr[] = result.user?.UserAttributes ?? [];

      const findValue = (name: string) =>
        attrs.find((a) => a.Name === name)?.Value || "";

      const userData: User = {
        username: result.user?.Username || "",
        email: findValue("email"),
        firstName: findValue("given_name") || findValue("first_name"),
        lastName: findValue("family_name") || findValue("last_name"),
      };

      setUser(userData);
      setIsAuthenticated(true);

      if (userData.firstName) {
        sessionStorage.setItem("userFirstName", userData.firstName);
      }

      return true;
    } catch (error) {
      console.log("ℹ️ Auth check failed");
      setUser(null);
      setIsAuthenticated(false);
      return false;
    }
  }, []);

  // ==================== AUTH METHODS ====================

  const login = useCallback(
    async (data: LoginData) => {
      await RestApiService.login(data);
      const authenticated = await checkAuth();

      if (authenticated) {
        startRefreshTimer();
        console.log("✅ Login successful");
      } else {
        throw new Error("Failed to authenticate after login");
      }
    },
    [checkAuth, startRefreshTimer]
  );

  const logout = useCallback(async () => {
    try {
      const sessionId =
        localStorage.getItem("chatbot_session_id") ||
        sessionStorage.getItem("chatbot_session_id");
      await RestApiService.logout(sessionId || undefined);
      console.log("✅ Logout successful");
    } catch (error) {
      console.error("Logout error:", error);
    } finally {
      setUser(null);
      setIsAuthenticated(false);
      sessionStorage.clear();
      localStorage.clear();
      stopRefreshTimer();

      if (window.location.pathname !== "/login") {
        router.push("/login");
      }
    }
  }, [router, stopRefreshTimer]);

  const signup = useCallback(async (data: SignupData) => {
    await RestApiService.signup(data);
    console.log("✅ Signup successful");
  }, []);

  const confirmSignup = useCallback(async (data: ConfirmData) => {
    await RestApiService.confirmSignup(data);
    console.log("✅ Email confirmed successfully");
  }, []);

  const forgotPassword = useCallback(async (username: string) => {
    await RestApiService.forgotPassword(username);
    console.log("✅ Reset code sent");
  }, []);

  const confirmForgotPassword = useCallback(
    async (data: { username: string; code: string; newPassword: string }) => {
      await RestApiService.confirmForgotPassword(data);
      console.log("✅ Password reset successful");
    },
    []
  );

  const resendConfirmation = useCallback(async (username: string) => {
    await RestApiService.resendConfirmation(username);
    console.log("✅ Verification code resent");
  }, []);

  // ==================== CHAT METHODS ====================

  const sendChatMessage = useCallback(
    async (prompt: string, sessionId: string): Promise<ChatResponse> => {
      return await RestApiService.sendChatMessage(prompt, sessionId);
    },
    []
  );

  const getChatHistory = useCallback(
    async (sessionId: string): Promise<HistoryResponse> => {
      return await RestApiService.getChatHistory(sessionId);
    },
    []
  );

  // ==================== INITIAL AUTH CHECK ====================
  useEffect(() => {
    const initAuth = async () => {
      setIsLoading(true);
      const authenticated = await checkAuth();

      if (authenticated) {
        startRefreshTimer();
      }

      setIsLoading(false);
    };

    initAuth();

    return () => {
      stopRefreshTimer();
    };
  }, [checkAuth, startRefreshTimer, stopRefreshTimer]);

  // ==================== REDIRECT LOGIC ====================

  useEffect(() => {
    if (isLoading) return; // Wait for initial auth check

    const currentPath = window.location.pathname;

    if (!isAuthenticated && currentPath !== "/login") {
      // Unauthenticated user on protected page → redirect to login
      console.log("🔒 User not authenticated, redirecting to login");
      router.replace("/login"); 
    } else if (isAuthenticated && currentPath === "/login") {
      // Authenticated user on login page → redirect to home
      console.log("✅ User already authenticated, redirecting to home");
      router.replace("/"); // ← replace kullan
    }
  }, [isAuthenticated, isLoading, router]);

  const value = {
    isAuthenticated,
    isLoading,
    user,
    login,
    logout,
    signup,
    confirmSignup,
    forgotPassword,
    confirmForgotPassword,
    resendConfirmation,
    checkAuth,
    sendChatMessage,
    getChatHistory,
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ==================== CUSTOM HOOK ====================
export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
