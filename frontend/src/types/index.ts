export type UserRole = "admin" | "supervisor" | "employee";

export interface User {
  id: number;
  employee_id: string;
  username: string;
  role: UserRole;
  supervisor_id: number | null;
  is_active: boolean;
  created_at: string;
}

export type ImageStatus = "pending" | "processing" | "success" | "failed";

export interface ImageVersion {
  id: number;
  image_id: number;
  version_number: number;
  ratio_width: number;
  ratio_height: number;
  min_short_side_px: number;
  output_width: number;
  output_height: number;
  file_size: number;
  compression_setting: string;
  created_at: string;
}

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
  current_version_number: number | null;
  file_size: number;
  content_type: string;
  status: ImageStatus;
  error_message: string | null;
  created_at: string;
  processed_at: string | null;
}

export interface ImagePage {
  items: ImageItem[];
  total: number;
  page: number;
  page_size: number;
}

export type LogCategory = "auth" | "user" | "image" | "processing";
export type LogStatus = "success" | "failed" | "info";

export interface OperationLog {
  id: number;
  category: LogCategory;
  action: string;
  status: LogStatus;
  actor_username: string | null;
  employee_id: string | null;
  image_id: number | null;
  target: string | null;
  message: string;
  details: string | null;
  created_at: string;
}

export interface UploadFileResult {
  filename: string;
  success: boolean;
  image: ImageItem | null;
  error: string | null;
}
