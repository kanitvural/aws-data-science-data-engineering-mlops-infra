// app/(home)/page.tsx
"use client";

import { useAuth } from "@/contexts/AuthContext";
import FlightDashboard from "@/components/FlightDashboard";

export default function Home() {
  const { isLoading, isAuthenticated } = useAuth();

  // Bekleme ekranı
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  // Not authenticated → AuthContext redirect 
  if (!isAuthenticated) {
    return null;
  }

  // İf auth Auth succeed show dashboard
  return <FlightDashboard />;
}

