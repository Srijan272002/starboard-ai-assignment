import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// This function can be marked `async` if using `await` inside
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  
  // Log direct API requests for debugging
  if (pathname === '/properties' || pathname.startsWith('/properties/')) {
    console.log(`[Middleware] API request detected: ${pathname}`);
  }
  
  // Redirect old URL pattern /properties/{id} to new pattern /properties/cook/{id}
  if (pathname.match(/^\/properties\/(?!cook|dallas|la)[^\/]+$/)) {
    const id = pathname.split('/').pop();
    const newUrl = request.nextUrl.clone();
    newUrl.pathname = `/properties/cook/${id}`;
    console.log(`[Middleware] Redirecting from ${pathname} to ${newUrl.pathname}`);
    return NextResponse.redirect(newUrl);
  }
  
  // Continue with the request
  return NextResponse.next();
}

// See "Matching Paths" below to learn more
export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    '/((?!_next/static|_next/image|favicon.ico).*)',
  ],
}; 