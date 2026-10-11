"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError, type User } from "./api";

/** Fetches the current user; redirects to /login on 401. Pass `requireRole` to also
 * redirect away (to /dashboard) when the user's role isn't in the allowed list -
 * convenience only, the backend is the real enforcement (ARCHITECTURE.md section 7). */
export function useUser(requireRole?: User["role"][]) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .me()
      .then((u) => {
        if (requireRole && !requireRole.includes(u.role)) {
          router.replace("/dashboard");
          return;
        }
        setUser(u);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          router.replace("/login");
        } else {
          setError("Could not load the current user.");
        }
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  return { user, error };
}
