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

function handleApiError(
  response: Response,
  result: any = {},
  defaultMessage: string
) {
  if (!response.ok) {
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
      sessionStorage.setItem("chatbot_session_id", result.sessionId);
      console.log("🆔 Session ID received from backend:", result.sessionId);
    }

    return result;
  }

  // UPDATED: Logout with sessionId
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

  // Get current user
  static async getCurrentUser() {
    const response = await fetch(`${apiGatewayRestUrl}/auth/me`, {
      method: "GET",
      credentials: "include",
    });

    const result = await response.json();

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
    const response = await fetch(`${apiGatewayRestUrl}/chat`, {
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
    const response = await fetch(
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
