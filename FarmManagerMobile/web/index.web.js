import { AppRegistry } from "react-native";
import materialCommunityIconsFont from "react-native-vector-icons/Fonts/MaterialCommunityIcons.ttf";

const iconFontStyle = document.createElement("style");
iconFontStyle.appendChild(
  document.createTextNode(`
    @font-face {
      src: url(${materialCommunityIconsFont});
      font-family: "MaterialCommunityIcons";
      font-display: block;
    }
  `)
);
document.head.appendChild(iconFontStyle);

// 全局错误捕获，白屏时显示错误信息
const root = document.getElementById("root");
const showError = (title, detail) => {
  if (root) {
    root.innerHTML = `
      <div style="padding:20px;font-family:-apple-system,sans-serif;">
        <h2 style="color:#e74c3c;font-size:18px;margin-bottom:12px;">${title}</h2>
        <pre style="background:#f5f5f5;padding:12px;border-radius:8px;font-size:13px;overflow:auto;white-space:pre-wrap;word-break:break-all;">${detail}</pre>
      </div>
    `;
  }
};

window.onerror = (msg, url, line, col, err) => {
  showError(
    "Runtime Error",
    `${msg}\n at ${url}:${line}:${col}\n${err?.stack || ""}`
  );
  return false;
};

window.onunhandledrejection = (e) => {
  showError(
    "Unhandled Promise Rejection",
    `${e.reason}\n${e.reason?.stack || ""}`
  );
};

try {
  const App = require("../App").default;
  const { name: appName } = require("../app.json");

  AppRegistry.registerComponent(appName, () => App);
  AppRegistry.runApplication(appName, {
    initialProps: {},
    rootTag: root,
  });
} catch (e) {
  showError("Module Load Error", `${e.message}\n${e.stack || ""}`);
}
