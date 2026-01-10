'use client';

import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { User as FirebaseUser, onAuthStateChanged } from 'firebase/auth';
import { auth } from '@/lib/firebase';
import { initializeAuth, getCurrentUser, AuthUser } from '@/lib/auth';

interface AuthContextType {
  user: AuthUser | null;
  loading: boolean;
  initialized: boolean;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  initialized: false,
});

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    let mounted = true;

    // Initialize regular auth (no demo mode)
    initializeAuth().then((authUser) => {
      if (mounted) {
        setUser(authUser);
        setLoading(false);
        setInitialized(true);
      }
    });

    // Listen for auth state changes
    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser: FirebaseUser | null) => {
      if (mounted) {
        if (firebaseUser) {
          // User is signed in - check localStorage first for cached user info
          const storedUser = localStorage.getItem('auth_user');
          if (storedUser) {
            try {
              const parsedUser = JSON.parse(storedUser);
              setUser(parsedUser);
            } catch {
              // Fall back to in-memory user
              setUser(getCurrentUser());
            }
          } else {
            // No stored user, use in-memory
            setUser(getCurrentUser());
          }
        } else {
          // User is signed out
          setUser(null);
        }
        setLoading(false);
        setInitialized(true);
      }
    });

    return () => {
      mounted = false;
      unsubscribe();
    };
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, initialized }}>
      {children}
    </AuthContext.Provider>
  );
}
