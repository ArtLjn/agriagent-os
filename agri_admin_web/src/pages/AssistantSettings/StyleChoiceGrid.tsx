import { CheckOutlined } from "@ant-design/icons";
import type { ReplyStyle } from "../../api/personalization";
import { REPLY_STYLE_OPTIONS } from "./options";

interface StyleChoiceGridProps {
  value?: ReplyStyle;
  onChange?: (value: ReplyStyle) => void;
}

export default function StyleChoiceGrid({ value, onChange }: StyleChoiceGridProps) {
  return (
    <div className="choice-grid" role="radiogroup" aria-label="回复风格">
      {REPLY_STYLE_OPTIONS.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={active}
            className="choice-card"
            data-active={active}
            onClick={() => onChange?.(option.value)}
          >
            <span className="choice-card__label">
              {option.label}
              <CheckOutlined className="choice-card__check" />
            </span>
            <span className="choice-card__desc">{option.description}</span>
          </button>
        );
      })}
    </div>
  );
}
