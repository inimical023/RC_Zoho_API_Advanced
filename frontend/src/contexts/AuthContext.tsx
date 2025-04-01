import React, { createContext, useState, useContext, useEffect } from 'react';
import api from '../services/api';

// Types
interface User {
  id: number;
  username: string;
  email: string;
  full_name?: string;
  is_admin: boolean;
}

interface AuthContextData {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: User | null;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
}

interface LoginResponse {
  access_token: string;
  token_type: string;
}

// Create context
const AuthContext = createContext<AuthContextData>({} as AuthContextData);

// Provider component
export const AuthProvider: React.FC<{children: React.ReactNode}> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  
  // Check if token exists in localStorage on mount
  useEffect(() => {
    const loadUserData = async () => {
      setIsLoading(true);
      const token = localStorage.getItem('token');
      
      if (token) {
        try {
          // Set Auth header with token
          api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
          
          // Fetch user info
          const response = await api.get('/api/auth/me');
          setUser(response.data);
        } catch (error) {
          console.error("Error loading user data:", error);
          // Token is invalid or expired
          localStorage.removeItem('token');
          api.defaults.headers.common['Authorization'] = '';
        }
      }
      
      setIsLoading(false);
    };
    
    loadUserData();
  }, []);
  
  // Login function
  const login = async (username: string, password: string): Promise<boolean> => {
    try {
      const response = await api.post<LoginResponse>('/api/auth/token', {
        username,
        password
      }, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      });
      
      const { access_token } = response.data;
      
      // Save token to localStorage
      localStorage.setItem('token', access_token);
      
      // Set auth header
      api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
      
      // Fetch user info
      const userResponse = await api.get('/api/auth/me');
      setUser(userResponse.data);
      
      return true;
    } catch (error) {
      console.error("Login error:", error);
      return false;
    }
  };
  
  // Logout function
  const logout = () => {
    // Remove token from localStorage
    localStorage.removeItem('token');
    
    // Remove auth header
    api.defaults.headers.common['Authorization'] = '';
    
    // Clear user data
    setUser(null);
  };
  
  return (
    <AuthContext.Provider value={{
      isAuthenticated: !!user,
      isLoading,
      user,
      login,
      logout
    }}>
      {children}
    </AuthContext.Provider>
  );
};

// Hook for using Auth context
export const useAuth = () => {
  const context = useContext(AuthContext);
  
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  
  return context;
}; 