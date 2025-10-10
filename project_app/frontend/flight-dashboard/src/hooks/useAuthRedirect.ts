// src/hooks/useAuthRedirect.ts
"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { RestApiService } from "@/services/restApiService";

export function useAuthRedirect(requireAuth: boolean = true) {
  const router = useRouter();
  const pathname = usePathname();
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    async function checkAuth() {
      try {
        await RestApiService.getCurrentUser();
        setIsAuthenticated(true);

        // Route to home if the user has an auth token.
        if (!requireAuth && pathname === "/login") {
          router.replace("/");
        }
      } catch (error) {
        setIsAuthenticated(false);

        // Route to login page if the user has not an auth token.
        if (requireAuth && pathname !== "/login") {
          router.replace("/login");
        }
      } finally {
        setIsLoading(false);
      }
    }

    checkAuth();
  }, [requireAuth, router, pathname]);

  return { isLoading, isAuthenticated };
}
