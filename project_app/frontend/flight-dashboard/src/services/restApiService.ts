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

    if (!response.ok) {
      throw new Error(result.error || "Signup failed");
    }

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

    if (!response.ok) {
      throw new Error(result.error || "Confirmation failed");
    }

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

    if (!response.ok) {
      throw new Error(result.error || "Login failed");
    }

    return result;
  }

  // Logout
  static async logout() {
    const response = await fetch(`${apiGatewayRestUrl}/auth/logout`, {
      method: "POST",
      credentials: "include",
    });

    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.error || "Logout failed");
    }

    return result;
  }

  // Get current user
  static async getCurrentUser() {
    const response = await fetch(`${apiGatewayRestUrl}/auth/me`, {
      method: "GET",
      credentials: "include",
    });

    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.error || "Failed to get user");
    }

    return result;
  }

  // Refresh token
  static async refreshToken() {
    const response = await fetch(`${apiGatewayRestUrl}/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });

    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.error || "Token refresh failed");
    }

    return result;
  }

  // Forgot password
  static async forgotPassword(username: string) {
    const response = await fetch(
      `${apiGatewayRestUrl}/user/forgot-password`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ username }),
      }
    );

    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.error || "Failed to send reset code");
    }

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

    if (!response.ok) {
      throw new Error(result.error || "Password reset failed");
    }

    return result;
  }

  // ==================== CHATBOT METHODS ====================

  // Send chat message
  static async sendChatMessage(prompt: string, sessionId: string): Promise<ChatResponse> {
    const response = await fetch(`${apiGatewayRestUrl}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "include",
      body: JSON.stringify({ prompt, sessionId }),
    });

    if (!response.ok) {
      throw new Error(`Chat request failed: ${response.status}`);
    }

    const result = await response.json();
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

    if (!response.ok) {
      throw new Error(`History fetch failed: ${response.status}`);
    }

    const result = await response.json();
    return result;
  }
}