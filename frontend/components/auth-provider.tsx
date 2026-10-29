"use client";

import { createContext, useContext, useEffect, useState } from "react";

import { api, refreshSession, setAccessToken } from "@/lib/api";
import type { TokenResponse, User } from "@/lib/types";

type AuthContextValue = {
  user: User | null;
  ready: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  async function refreshUser() {
    const me = await api<User>("/users/me");
    setUser(me);
  }

  useEffect(() => {
    let active = true;
    refreshSession()
      .then(async (signedIn) => {
        if (!active) {
          return;
        }
        if (signedIn) {
          try {
            await refreshUser();
          } catch {
            setUser(null);
          }
        }
      })
      .finally(() => {
        if (active) {
          setReady(true);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  async function signIn(email: string, password: string) {
    const token = await api<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setAccessToken(token.access_token);
    await refreshUser();
  }

  async function signOut() {
    try {
      await api<void>("/auth/logout", { method: "POST" });
    } finally {
      setAccessToken(null);
      setUser(null);
    }
  }

  return (
    <AuthContext.Provider value={{ user, ready, signIn, signOut, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }
  return value;
}
