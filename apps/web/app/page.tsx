import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ACCESS_COOKIE } from "@/lib/oidc";

export default async function HomePage() {
  const cookieStore = await cookies();
  redirect(cookieStore.has(ACCESS_COOKIE) ? "/organizations" : "/login");
}
