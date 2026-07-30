export type UserRole = "admin" | "employee";

export interface User {
  id: number;
  employee_id: string;
  username: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export type ImageStatus = "pending" | "processing" | "success" | "failed";

export interface ImageItem {
  id: number;
  employee_id: string;
  sku: string;
  original_filename: string;
  target_ratio_width: number;
  target_ratio_height: number;
  min_short_side_px: number;
  original_width: number | null;
  original_height: number | null;
  processed_width: number | null;
  processed_height: number | null;
  file_size: number;
  content_type: string;
  status: ImageStatus;
  error_message: string | null;
  created_at: string;
  processed_at: string | null;
}

export interface UploadFileResult {
  filename: string;
  success: boolean;
  image: ImageItem | null;
  error: string | null;
}
