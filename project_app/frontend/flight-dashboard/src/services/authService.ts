// src/services/authService.ts

// const API_BASE_URL =
//   "https://xmvydhhy8h.execute-api.eu-central-1.amazonaws.com/prod";

const API_GATEWAY_AUTH_URL = process.env.NEXT_PUBLIC_API_GATEWAY_AUTH_URL!;;
if (!API_GATEWAY_AUTH_URL) throw new Error("API Gateway Auth URL not found in sessionStorage");




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

export class AuthService {
  // Signup
  static async signup(data: SignupData) {
    const response = await fetch(`${API_GATEWAY_AUTH_URL}/user/signup`, {
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
    const response = await fetch(`${API_GATEWAY_AUTH_URL}/user/confirm`, {
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
    const response = await fetch(`${API_GATEWAY_AUTH_URL}/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "include", // Cookie için önemli!
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
    const response = await fetch(`${API_GATEWAY_AUTH_URL}/auth/logout`, {
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
    const response = await fetch(`${API_GATEWAY_AUTH_URL}/auth/me`, {
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
    const response = await fetch(`${API_GATEWAY_AUTH_URL}/auth/refresh`, {
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
    const response = await fetch(`${API_GATEWAY_AUTH_URL}/user/forgot-password`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ username }),
    });

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
      `${API_GATEWAY_AUTH_URL}/user/confirm-forgot-password`,
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
}
