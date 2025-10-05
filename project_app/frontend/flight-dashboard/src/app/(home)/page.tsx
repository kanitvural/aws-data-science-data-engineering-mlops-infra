// app/(home)/page.tsx
'use client';

import { useAuthRedirect } from "@/hooks/useAuthRedirect";
import FlightDashboard from "@/components/FlightDashboard"; 

export default function Home() {
  const { isLoading, isAuthenticated } = useAuthRedirect(true);

  // Auth kontrol edilirken loading göster

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  // Auth yoksa hiçbir şey render etme (hook zaten redirect ediyor)
  if (!isAuthenticated) {
    return null;
  }

  // Auth varsa dashboard göster
  return <FlightDashboard />; 
}




// import FlightDashboard from "@/components/FlightDashboard";

// export default function Home() {
//   return <FlightDashboard />;
// }
