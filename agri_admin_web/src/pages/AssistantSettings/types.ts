import type { PersonalizationSettings } from "../../api/personalization";

export type PersonalizationFormValues = Pick<
  PersonalizationSettings,
  | "nickname"
  | "assistant_name"
  | "reply_style"
  | "detail_level"
  | "display_format"
  | "custom_instructions"
  | "loading_greeting_enabled"
  | "execution_detail_level"
>;

export function toFormValues(
  settings: PersonalizationSettings,
): PersonalizationFormValues {
  return {
    nickname: settings.nickname,
    assistant_name: settings.assistant_name,
    reply_style: settings.reply_style,
    detail_level: settings.detail_level,
    display_format: settings.display_format,
    custom_instructions: settings.custom_instructions,
    loading_greeting_enabled: settings.loading_greeting_enabled,
    execution_detail_level: settings.execution_detail_level,
  };
}
