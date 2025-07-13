'use client'

import { type ReactNode, useEffect } from 'react';
import { useKeyboardShortcuts } from '@/lib/shortcuts';

interface ClientLayoutProps {
  children: ReactNode;
}

export function ClientLayout({ children }: ClientLayoutProps) {
  useKeyboardShortcuts();

  // Remove the cz-shortcut-listen attribute on mount
  useEffect(() => {
    document.body.removeAttribute('cz-shortcut-listen');
  }, []);

  return children;
} 