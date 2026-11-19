"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { getToken } from "@/lib/auth";

export function useAuthGate(): { ready: boolean; authed: boolean } {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login");
      setAuthed(false);
    } else {
      setAuthed(true);
    }
    setReady(true);
  }, [router]);

  return { ready, authed };
}
