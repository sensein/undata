"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

export default function AuthCallbackPage() {
  const router = useRouter();
  const [status, setStatus] = useState("Processing sign in...");

  useEffect(() => {
    const hash = window.location.hash;
    const search = window.location.search;

    // Try fragment first: #token=...
    let token: string | null = null;
    if (hash) {
      const params = new URLSearchParams(hash.substring(1));
      token = params.get("token");
    }
    // Fallback: ?token=... (query parameter)
    if (!token && search) {
      const params = new URLSearchParams(search);
      token = params.get("token");
    }

    if (token) {
      localStorage.setItem("access_token", token);
      setStatus("Sign in successful! Redirecting...");
      setTimeout(() => router.replace("/"), 500);
    } else {
      setStatus("Sign in failed — no token received. Redirecting...");
      setTimeout(() => router.replace("/"), 3000);
    }
  }, [router]);

  return (
    <div className="flex items-center justify-center py-20">
      <p className="text-gray-500">{status}</p>
    </div>
  );
}
