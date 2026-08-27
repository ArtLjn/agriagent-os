import axios from "axios";
import { message } from "antd";
import { authStore } from "../stores/authStore";

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 120000,
  headers: { "Content-Type": "application/json" },
});

type ApiErrorField = { loc?: unknown[]; msg?: string; field?: string; message?: string };

export function parseApiError(payload: unknown): {
  code?: string;
  message?: string;
  fields: string[];
} {
  const data = payload && typeof payload === "object" ? payload as Record<string, unknown> : {};
  const detail = data.detail;
  const detailObject = detail && typeof detail === "object" ? detail as Record<string, unknown> : null;
  const code = typeof detailObject?.code === "string" ? detailObject.code : undefined;
  const message = typeof detailObject?.message === "string"
    ? detailObject.message
    : typeof detail === "string" ? detail : undefined;
  const metaErrors = detailObject?.meta && typeof detailObject.meta === "object"
    ? (detailObject.meta as Record<string, unknown>).errors : undefined;
  const errors = Array.isArray(metaErrors) ? metaErrors : Array.isArray(data.errors) ? data.errors : [];
  const fields = errors.map((item) => {
    const error = item as ApiErrorField;
    const location = Array.isArray(error.loc) ? error.loc.join(".") : error.field;
    return location ? `${location}: ${error.msg || error.message || "参数错误"}` : error.msg || error.message || "参数错误";
  });
  return {
    ...(code ? { code } : {}),
    ...(message ? { message } : {}),
    fields,
  };
}

apiClient.interceptors.request.use(
  (config) => {
    const token = authStore.getToken();
    // 允许 Playground 用 dev 用户 token 覆盖默认管理员登录态。
    if (token && !config.headers?.Authorization) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const status = error.response.status;
      const data = error.response.data;

      if (status === 401) {
        authStore.clearToken();
        window.location.href = "/login";
        return Promise.reject(new Error("登录已过期"));
      }
      if (status === 429) {
        message.error("请求过于频繁，请稍后再试");
      } else if (status === 422) {
        const parsed = parseApiError(data);
        message.error(`参数错误：${parsed.fields.join("；") || parsed.message || "未知错误"}`);
      } else if (status >= 500) {
        message.error(parseApiError(data).message || "服务器异常，请稍后再试");
      } else {
        message.error(parseApiError(data).message || "请求失败");
      }
    } else if (error.request) {
      message.error("网络错误，请检查连接");
    } else {
      message.error("请求配置错误");
    }
    return Promise.reject(error);
  }
);

export default apiClient;
