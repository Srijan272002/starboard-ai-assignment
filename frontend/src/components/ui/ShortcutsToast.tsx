import { type Shortcut } from '@/lib/shortcuts';

interface ShortcutsToastProps {
  shortcuts: Shortcut[];
}

export function ShortcutsToast({ shortcuts }: ShortcutsToastProps) {
  return (
    <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-lg">
      <h3 className="font-semibold mb-2">Keyboard Shortcuts</h3>
      <ul className="space-y-2">
        {shortcuts.map((shortcut) => (
          <li key={shortcut.key} className="flex items-center justify-between">
            <kbd className="px-2 py-1 text-xs font-semibold bg-gray-100 dark:bg-gray-700 border rounded-md">
              {shortcut.key}
            </kbd>
            <span className="ml-4 text-sm">{shortcut.description}</span>
          </li>
        ))}
      </ul>
    </div>
  );
} 