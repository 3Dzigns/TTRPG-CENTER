import type { Metadata } from "next";
import { SignInForm } from "./sign-in-form";

export const metadata: Metadata = {
  title: "Sign In - TTRPG Center"
};

interface SignInPageProps {
  searchParams: Promise<{ redirect?: string }>;
}

export default async function SignInPage({ searchParams }: SignInPageProps) {
  const params = await searchParams;
  const redirect = params.redirect ?? "/player";
  return (
    <main
      id="main-content"
      tabIndex={-1}
      className="flex min-h-screen items-center justify-center bg-surface-50 p-6 focus:outline-none dark:bg-surface-900"
    >
      <SignInForm redirectPath={redirect} />
    </main>
  );
}
