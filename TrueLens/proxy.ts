import { clerkMiddleware } from '@clerk/nextjs/server'
import { NextResponse } from 'next/server';
import type { NextRequest, NextFetchEvent } from 'next/server';

const clerkKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
const isClerkConfigured = clerkKey && clerkKey.startsWith('pk_') && !clerkKey.includes('placeholder');

// Create the Clerk middleware handler
const authMiddleware = clerkMiddleware(async (auth, req: NextRequest) => {
  const { pathname } = req.nextUrl;
  if (pathname.startsWith('/dashboard')) {
    await auth.protect();
  }
});

// For Next.js 16+, proxy.ts must export a function named proxy or a default function.
// We explicitly define proxy function to wrap Clerk middleware and avoid adapterFn type issues
export async function proxy(request: NextRequest, event: NextFetchEvent) {
  if (isClerkConfigured) {
    return authMiddleware(request, event);
  }
  return NextResponse.next();
}

export const config = {
  matcher: [
    // Skip Next.js internals and all static files
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    // Always run for API routes
    '/(api|trpc)(.*)',
  ],
}
