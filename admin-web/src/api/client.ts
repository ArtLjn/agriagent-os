import axios from "axios";
import { message } from "antd";
import { authStore } from "../stores/authStore";

const apiClient = axios.create({
  baseURL: "/api",
  timeout: 120000,
  headers: { "Content-Type": "application/json" },
});

apiClient.interceptors.request.use(
  (config) => {
    const token = authStore.getToken();
    if (token) {
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
        const details = data.errors?.map((e: { field: string; message: string }) => `${e.field}: ${e.message}`).join("；") || data.detail;
        message.error(`参数错误：${details}`);
      } else if (status >= 500) {
        message.error("服务器异常，请稍后再试");
      } else {
        message.error(data.detail || "请求失败");
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
