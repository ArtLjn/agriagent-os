import type { DetailLevel, ReplyStyle } from "../../api/personalization";
import {
  DETAIL_LEVEL_OPTIONS,
  REPLY_STYLE_OPTIONS,
} from "./options";
import type { PersonalizationFormValues } from "./types";

interface PreviewCardProps {
  values: PersonalizationFormValues;
}

const INTRO_BY_STYLE: Record<ReplyStyle, string> = {
  default: "建议今天傍晚浇水。",
  friendly: "建议今天傍晚浇一次水，别着急大水漫灌～",
  professional: "结论：建议于今日傍晚灌溉。",
  efficient: "傍晚浇水，先测湿度。",
};

const DETAIL_TEXT: Record<DetailLevel, string> = {
  concise: "",
  balanced: "三号棚表层土偏干，辣椒正处于坐果期，保持土壤湿润更稳。",
  detailed:
    "三号棚表层土偏干，辣椒正处于坐果期，稳定水分更有利于坐果。建议小水勤浇，避免积水。",
};

const DETAIL_POINTS = [
  "表层土壤偏干，午后蒸发量大",
  "处于坐果期，对水分波动更敏感",
  "傍晚浇水可减少蒸发损失",
];

function optionLabel<T extends string>(
  options: { value: T; label: string }[],
  value: T,
): string {
  return options.find((option) => option.value === value)?.label ?? value;
}

export default function PreviewCard({ values }: PreviewCardProps) {
  const assistantName = values.assistant_name.trim() || "田掌柜";
  const initial = assistantName.slice(0, 1);
  const intro = INTRO_BY_STYLE[values.reply_style];
  const detail = DETAIL_TEXT[values.detail_level];
  const wantsList =
    values.display_format === "list" || values.detail_level === "detailed";
  const wantsTable = values.display_format === "table";

  return (
    <div className="preview-card">
      <div className="preview-card__head">
        <span className="preview-card__live" />
        实时预览
      </div>

      <div className="preview-chat">
        <div className="preview-bubble--user">三号棚的辣椒今天要浇水吗？</div>
        <div className="preview-assistant">
          <div className="preview-avatar" aria-hidden="true">
            {initial}
          </div>
          <div className="preview-bubble--assistant">
            <div className="preview-bubble__name">{assistantName}</div>
            <div>
              {intro}
              {detail ? ` ${detail}` : ""}
            </div>
            {wantsList && (
              <ul className="preview-list">
                {DETAIL_POINTS.slice(0, values.detail_level === "detailed" ? 3 : 2).map(
                  (point) => (
                    <li key={point}>{point}</li>
                  ),
                )}
              </ul>
            )}
            {wantsTable && (
              <table className="preview-mini-table">
                <thead>
                  <tr>
                    <th>判断项</th>
                    <th>建议</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>土壤湿度</td>
                    <td>低于 60% 时浇水</td>
                  </tr>
                  <tr>
                    <td>浇水时段</td>
                    <td>傍晚，小水勤浇</td>
                  </tr>
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      <div className="preview-meta">
        <span>
          按「{optionLabel(REPLY_STYLE_OPTIONS, values.reply_style)} ·{" "}
          {optionLabel(DETAIL_LEVEL_OPTIONS, values.detail_level)}」生成
        </span>
        <span>{values.custom_instructions.trim() ? "已应用自定义指令" : "仅预览"}</span>
      </div>
    </div>
  );
}
