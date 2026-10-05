import { NextResponse } from "next/server";
import { reset } from "@/lib/store";

export const dynamic = "force-dynamic";

// POST for API clients; GET so Selenium IDE can reset state with a plain `open`.
export async function POST() {
  reset();
  return NextResponse.json({ ok: true });
}

export const GET = POST;
