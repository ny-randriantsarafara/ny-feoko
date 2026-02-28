"use client";

import { useEffect, useState, useCallback } from "react";

export interface ToastData {
  readonly id: string;
  readonly message: string;
  readonly action?: {
    readonly label: string;
    readonly onClick: () => void;
  };
  readonly durationMs?: number;
}

interface ToastItemProps {
  readonly toast: ToastData;
  readonly onDismiss: (id: string) => void;
}

function ToastItem({ toast, onDismiss }: ToastItemProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    requestAnimationFrame(() => setVisible(true));
  }, []);

  useEffect(() => {
    const duration = toast.durationMs ?? 5000;
    const timer = setTimeout(() => {
      setVisible(false);
      setTimeout(() => onDismiss(toast.id), 300);
    }, duration);
    return () => clearTimeout(timer);
  }, [toast.id, toast.durationMs, onDismiss]);

  const handleAction = useCallback(() => {
    toast.action?.onClick();
    setVisible(false);
    setTimeout(() => onDismiss(toast.id), 300);
  }, [toast, onDismiss]);

  return (
    <div
      className={`flex items-center gap-3 px-4 py-3 rounded-lg bg-[#1a1a2e] border border-[#2a2a4a] shadow-lg text-sm text-gray-200 transition-all duration-300 ${
        visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-2"
      }`}
    >
      <span className="flex-1">{toast.message}</span>
      {toast.action && (
        <button
          onClick={handleAction}
          className="shrink-0 px-3 py-1 rounded bg-blue-700 hover:bg-blue-600 text-white text-xs font-medium transition-colors"
        >
          {toast.action.label}
        </button>
      )}
    </div>
  );
}

interface ToastContainerProps {
  readonly toasts: readonly ToastData[];
  readonly onDismiss: (id: string) => void;
}

export default function ToastContainer({ toasts, onDismiss }: ToastContainerProps) {
  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>
  );
}
