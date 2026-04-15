"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function AuthCallbackPage() {
  const router = useRouter();

  useEffect(() => {
    const hash = window.location.hash;
    const search = window.location.search;

    let token: string | null = null;
    if (hash) {
      const params = new URLSearchParams(hash.substring(1));
      token = params.get("token");
    }
    if (!token && search) {
      const params = new URLSearchParams(search);
      token = params.get("token");
    }

    if (token) {
      localStorage.setItem("access_token", token);
    }
    // Always redirect — if token was set, AuthProvider picks it up on /
    router.replace("/");
  }, [router]);

  return (
    <div className="flex items-center justify-center py-20">
      <p className="text-gray-500">Completing sign in...</p>
    </div>
  );
}
