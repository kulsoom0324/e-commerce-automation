"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

interface AuthContextValue {
  authenticatedUser: string | null;
  setAuthenticatedUser: (user: string | null) => void;
  isAuthenticated: boolean;
  isHydrated: boolean;
  login: (user: string | null) => void;
  logout: () => void;
}

const STORAGE_KEY = "digital-fte-auth";

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [authenticatedUser, setAuthenticatedUser] = useState<string | null>(null);
  const [isHydrated, setIsHydrated] = useState(false);
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as { user?: string | null };
        if (parsed?.user) {
          setAuthenticatedUser(parsed.user);
        }
      }
    } catch {
      // Ignore storage errors and continue with unauthenticated state.
    } finally {
      setIsHydrated(true);
    }
  }, []);

  useEffect(() => {
    if (!isHydrated) return;

    try {
      if (authenticatedUser) {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ user: authenticatedUser }));
      } else {
        window.localStorage.removeItem(STORAGE_KEY);
      }
    } catch {
      // Ignore storage write failures.
    }
  }, [authenticatedUser, isHydrated]);

  useEffect(() => {
    if (!isHydrated) return;

    if (authenticatedUser && pathname === "/") {
      router.replace("/dashboard");
    }

    if (!authenticatedUser && pathname.startsWith("/dashboard")) {
      router.replace("/");
    }
  }, [authenticatedUser, isHydrated, pathname, router]);

  const login = (user: string | null) => {
    setAuthenticatedUser(user);
  };

  const logout = () => {
    setAuthenticatedUser(null);
  };

  const value = useMemo<AuthContextValue>(
    () => ({
      authenticatedUser,
      setAuthenticatedUser,
      isAuthenticated: Boolean(authenticatedUser),
      isHydrated,
      login,
      logout,
    }),
    [authenticatedUser, isHydrated]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
