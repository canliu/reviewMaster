import { toast as sonnerToast } from "sonner";

// Thin shortcut wrapper so callers don't need to know we're on Sonner.
// Centralizing this means swapping toast libs later is a one-file change.
export const useToast = () => ({
  success: (message: string, description?: string) =>
    sonnerToast.success(message, { description }),
  error: (message: string, description?: string) =>
    sonnerToast.error(message, { description }),
  info: (message: string, description?: string) =>
    sonnerToast.info(message, { description }),
  warning: (message: string, description?: string) =>
    sonnerToast.warning(message, { description }),
});
