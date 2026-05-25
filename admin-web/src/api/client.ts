import axios from "axios";
import { message } from "antd";

const apiClient = axios.create({
  baseURL: "/api",
  timeout: 120000,
  headers: { "Content-Type": "application/json" },
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const status = error.response.status;
      const data = error.response.data;

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
  },
);

export default apiClient;
