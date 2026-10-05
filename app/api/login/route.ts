import { NextResponse } from "next/server";
import { authenticate, SESSION_COOKIE } from "@/lib/store";

export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));
  const user = authenticate(String(body.email ?? ""), String(body.password ?? ""));
  if (!user) {
    return NextResponse.json({ error: "Invalid email or password" }, { status: 401 });
  }
  const res = NextResponse.json({ user });
  res.cookies.set(SESSION_COOKIE, user.userId, { path: "/", sameSite: "lax" });
  return res;
}
