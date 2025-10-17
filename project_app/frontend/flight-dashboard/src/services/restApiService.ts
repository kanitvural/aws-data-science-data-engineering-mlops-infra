// src/services/authService.ts

const apiGatewayRestUrl = process.env.NEXT_PUBLIC_API_GATEWAY_REST_URL || "";

export interface SignupData {
  username: string;
  password: string;
  email: string;
  firstName: string;
  lastName: string;
  gender: string;
}

export interface LoginData {
  username: string;
  password: string;
}

export interface ConfirmData {
  username: string;
  code: string;
}

export interface ChatMessage {
  id: string;
  text: string;
  isUser: boolean;
}

export interface ChatResponse {
  response: string;
}

export interface HistoryItem {
  eventId: string;
  content: string;
  role: string;
  timestamp: string;
}

export interface HistoryResponse {
  history: HistoryItem[];
  count: number;
}

// Token refresh state (prevent multiple simultaneous refresh attempts)
let isRefreshing = false;
let refreshPromise: Promise<boolean> | null = null;

// Refresh token and retry failed request

async function refreshAndRetry(
  originalRequest: () => Promise<Response>
): Promise<Response> {
  // If already refreshing, wait for it
  if (isRefreshing && refreshPromise) {
    console.log("⏳ Waiting for ongoing token refresh...");
    await refreshPromise;
    return originalRequest();
  }

  isRefreshing = true;
  refreshPromise = (async () => {
    try {
      console.log("🔄 Access token expired, refreshing...");
      await RestApiService.refreshToken();
      console.log("✅ Token refreshed, retrying original request");
      return true;
    } catch (error) {
      console.error("❌ Token refresh failed:", error);
      // Don't redirect here - just fail
      // AuthContext will handle redirect
      sessionStorage.clear();
      localStorage.clear();
      return false;
    } finally {
      isRefreshing = false;
      refreshPromise = null;
    }
  })();

  const refreshSuccess = await refreshPromise;

  if (refreshSuccess) {
    return originalRequest();
  } else {
    // Throw error - component will handle
    throw new Error("Session expired");
  }
}

// Wrapper for fetch with auto-retry on 401
async function fetchWithRetry(
  url: string,
  options: RequestInit
): Promise<Response> {
  const makeRequest = () => fetch(url, options);

  const response = await makeRequest();

  // If 401 and not already a refresh request, try to refresh and retry
  if (response.status === 401 && !url.includes("/auth/refresh")) {
    console.log("🔐 Received 401, attempting token refresh...");
    return refreshAndRetry(makeRequest);
  }

  return response;
}

function handleApiError(
  response: Response,
  result: any = {},
  defaultMessage: string
) {
  if (!response.ok) {
    // Special handling for 401 (will be caught by fetchWithRetry)
    if (response.status === 401) {
      throw new Error(result?.message || "Authentication required");
    }
    throw new Error(result?.message || result?.error || defaultMessage);
  }
}

export class RestApiService {
  // ==================== AUTH METHODS ====================

  // Signup
  static async signup(data: SignupData) {
    const response = await fetch(`${apiGatewayRestUrl}/user/signup`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });

    const result = await response.json();

    handleApiError(response, result, "Signup failed");
    return result;
  }

  // Confirm email
  static async confirmSignup(data: ConfirmData) {
    const response = await fetch(`${apiGatewayRestUrl}/user/confirm`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });

    const result = await response.json();

    handleApiError(response, result, "Confirmation failed");

    return result;
  }

  // Login
  static async login(data: LoginData) {
    const response = await fetch(`${apiGatewayRestUrl}/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "include",
      body: JSON.stringify(data),
    });

    const result = await response.json();

    handleApiError(response, result, "Login failed");

    // Save session id to session storage
    if (result.sessionId) {
      localStorage.setItem("chatbot_session_id", result.sessionId);
      sessionStorage.setItem("chatbot_session_id", result.sessionId);
      console.log("🆔 Session ID received from backend:", result.sessionId);
    }

    return result;
  }

  // Logout with sessionId
  static async logout(sessionId?: string) {
    const body = sessionId ? { sessionId } : {};

    const response = await fetch(`${apiGatewayRestUrl}/auth/logout`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "include",
      body: JSON.stringify(body),
    });

    const result = await response.json();
    handleApiError(response, result, "Logout failed");

    return result;
  }

  // Get current user (NO retry - for initial auth check)
  static async getCurrentUser() {
    const response = await fetch(`${apiGatewayRestUrl}/auth/me`, {
      method: "GET",
      credentials: "include",
    });

    const result = await response.json();

    // Don't throw on 401 - just return result
    if (response.status === 401) {
      return { error: "Not authenticated" };
    }

    handleApiError(response, result, "Failed to get user");
    return result;
  }

  // Refresh token
  static async refreshToken() {
    const response = await fetch(`${apiGatewayRestUrl}/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });

    const result = await response.json();

    handleApiError(response, result, "Token refresh failed");

    return result;
  }

  // Forgot password
  static async forgotPassword(username: string) {
    const response = await fetch(`${apiGatewayRestUrl}/user/forgot-password`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ username }),
    });

    const result = await response.json();

    handleApiError(response, result, "Failed to send reset code");

    return result;
  }

  // Confirm forgot password
  static async confirmForgotPassword(data: {
    username: string;
    code: string;
    newPassword: string;
  }) {
    const response = await fetch(
      `${apiGatewayRestUrl}/user/confirm-forgot-password`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username: data.username,
          code: data.code,
          new_password: data.newPassword,
        }),
      }
    );

    const result = await response.json();

    handleApiError(response, result, "Password reset failed");

    return result;
  }

  // Resend confirmation code
  static async resendConfirmation(username: string) {
    const response = await fetch(
      `${apiGatewayRestUrl}/user/resend-confirmation`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ username }),
      }
    );

    const result = await response.json();

    handleApiError(response, result, "Failed to resend verification code");

    return result;
  }

  // ==================== CHATBOT METHODS ====================

  // Send chat message
  static async sendChatMessage(
    prompt: string,
    sessionId: string
  ): Promise<ChatResponse> {
    const response = await fetchWithRetry(`${apiGatewayRestUrl}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "include",
      body: JSON.stringify({ prompt, sessionId }),
    });

    const result = await response.json();
    handleApiError(response, result, "Chat request failed");
    return result;
  }

  // Get chat history
  static async getChatHistory(sessionId: string): Promise<HistoryResponse> {
    const response = await fetchWithRetry(
      `${apiGatewayRestUrl}/history?sessionId=${sessionId}`,
      {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
      }
    );

    const result = await response.json();
    handleApiError(response, result, "History fetch failed");
    return result;
  }
}

// # fetch → fetchWithRetry?

// | Function                     | fetch → fetchWithRetry?               |
// |-------------------------------|--------------------------------------|
// | signup                        | ❌ No auth required                  |
// | confirmSignup                 | ❌ No auth required                  |
// | login                         | ❌ First auth, retry not needed      |
// | logout                        | ❌ Already logged out                |
// | getCurrentUser                | ✅ 401 → refresh → retry             |
// | refreshToken                  | ❌ It refreshes itself               |
// | forgotPassword                | ❌ No auth required                  |
// | confirmForgotPassword         | ❌ No auth required                  |
// | resendConfirmation            | ❌ No auth required                  |
// | sendChatMessage               | ✅ 401 → refresh → retry             |
// | getChatHistory                | ✅ 401 → refresh → retry             |
