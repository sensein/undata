"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function AuthCallbackPage() {
  const router = useRouter();

  useEffect(() => {
    // Read token from URL fragment: #token=...
    const hash = window.location.hash;
    const params = new URLSearchParams(hash.replace("#", ""));
    const token = params.get("token");

    if (token) {
      localStorage.setItem("access_token", token);
      // Clean URL and redirect to home
      router.replace("/");
    } else {
      router.replace("/?auth_error=no_token");
    }
  }, [router]);

  return (
    <div className="flex items-center justify-center py-20">
      <p className="text-gray-500">Completing sign in...</p>
    </div>
  );
}
