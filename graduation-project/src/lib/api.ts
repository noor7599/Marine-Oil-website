/**
 * API utility functions for authentication
 */

const BASE_URL = "http://localhost:5000";


export interface LoginRequest {
  email: string;
  password: string;
}

export interface AuthResponse {
  success: boolean;
  message: string;
  token?: string;
  user?: {
    id: string;
    email: string;
  };
}

export const api = {
  async login(credentials: LoginRequest): Promise<AuthResponse> {
    const response = await fetch(`${BASE_URL}/api/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(credentials),
    });

    return response.json();
  },

  async register(credentials: LoginRequest): Promise<AuthResponse> {
    const response = await fetch(`${BASE_URL}/api/auth/register`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(credentials),
    });

    return response.json();
  },

  async verify(token: string): Promise<AuthResponse> {
    const response = await fetch(`${BASE_URL}/api/auth/verify`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    return response.json();
  },

  getToken(): string | null {
    return localStorage.getItem("authToken");
  },

  setToken(token: string): void {
    localStorage.setItem("authToken", token);
  },

  clearToken(): void {
    localStorage.removeItem("authToken");
    localStorage.removeItem("user");
  },

  getUser() {
    const user = localStorage.getItem("user");
    return user ? JSON.parse(user) : null;
  },

  isLoggedIn(): boolean {
    return !!this.getToken();
  },
};