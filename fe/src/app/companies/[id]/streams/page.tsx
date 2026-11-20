"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

/** Streams editor moved to /companies/{id}/edit — redirect. */
export default function StreamsRedirectPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  useEffect(() => {
    if (params.id) router.replace(`/companies/${params.id}/edit`);
  }, [params.id, router]);
  return null;
}
