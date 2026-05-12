import axios from "axios";

// Stub axios instance. Auth interceptors are wired up in Stage 1.
export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000",
  headers: { "Content-Type": "application/json" },
});
