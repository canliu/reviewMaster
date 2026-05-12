import { api } from "@/lib/api";

export interface UploadBatch {
  id: string;
  filename: string;
  file_size_bytes: number;
  total_rows: number;
  new_rows: number;
  updated_rows: number;
  duplicate_rows: number;
  error_rows: number;
  progress: number;
  status: "processing" | "completed" | "failed";
  error_detail: Record<string, unknown> | null;
  started_at: string;
  completed_at: string | null;
}

export interface UploadEnqueued {
  batch_id: string;
  status: string;
}

export interface UploadList {
  items: UploadBatch[];
  total: number;
  page: number;
  page_size: number;
}

export async function uploadFile(file: File): Promise<UploadEnqueued> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post<UploadEnqueued>("/api/uploads", form, {
    // Let axios set the multipart boundary; the default JSON content-type
    // would break the upload.
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function getUpload(batchId: string): Promise<UploadBatch> {
  const { data } = await api.get<UploadBatch>(`/api/uploads/${batchId}`);
  return data;
}

export async function listUploads(
  page: number = 1,
  pageSize: number = 20,
): Promise<UploadList> {
  const { data } = await api.get<UploadList>("/api/uploads", {
    params: { page, page_size: pageSize },
  });
  return data;
}
