import { useEffect, useState } from "react";

// Returns a value that follows `input` after `delay` ms of stability.
export function useDebounce<T>(input: T, delay: number = 300): T {
  const [debounced, setDebounced] = useState(input);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(input), delay);
    return () => clearTimeout(id);
  }, [input, delay]);
  return debounced;
}
