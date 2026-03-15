import { getAuthorizeUrl } from "@/lib/auth";
import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.redirect(getAuthorizeUrl());
}
