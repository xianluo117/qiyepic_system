import { ElMessage } from "element-plus";

export async function copyConsoleText(value: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(value);
    ElMessage.success("已复制");
  } catch {
    ElMessage.warning("当前浏览器不支持自动复制，请选中文本手动复制");
  }
}
