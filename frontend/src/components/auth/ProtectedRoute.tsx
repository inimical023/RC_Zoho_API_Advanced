import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRole?: 'admin';
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ 
  children, 
  requiredRole 
}) => {
  const { isAuthenticated, user, isLoading } = useAuth();
  
  // If auth is still loading, show nothing
  if (isLoading) {
    return null;
  }
  
  // If not authenticated, redirect to login
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  // If a specific role is required, check it
  if (requiredRole === 'admin' && user && !user.is_admin) {
    // User is authenticated but doesn't have the required role
    return <Navigate to="/dashboard" replace />;
  }
  
  // User is authenticated and has the required role (or no specific role is required)
  return <>{children}</>;
};

export default ProtectedRoute; 