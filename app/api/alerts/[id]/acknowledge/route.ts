import { NextRequest, NextResponse } from "next/server";
import { acknowledgeAlert, SESSION_COOKIE } from "@/lib/store";

export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  // Calls without a session (e.g. from JMeter) are attributed to the single test user.
  const userId = req.cookies.get(SESSION_COOKIE)?.value ?? "USR-001";
  const alert = acknowledgeAlert(id, userId);
  if (!alert) {
    return NextResponse.json({ error: `Alert ${id} not found` }, { status: 404 });
  }
  return NextResponse.json(alert);
}
