import { Toaster as HotToaster } from 'react-hot-toast';

export function Toaster() {
  return (
    <HotToaster
      position="top-right"
      toastOptions={{
        className: '',
        duration: 5000,
        style: {
          background: 'var(--background)',
          color: 'var(--foreground)',
          border: '1px solid var(--border)',
        },
        success: {
          iconTheme: {
            primary: 'var(--success)',
            secondary: 'var(--background)',
          },
        },
        error: {
          iconTheme: {
            primary: 'var(--destructive)',
            secondary: 'var(--background)',
          },
        },
      }}
    />
  );
} 