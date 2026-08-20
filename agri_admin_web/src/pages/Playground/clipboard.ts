interface AsyncClipboardItemData {
  [mimeType: string]: Promise<Blob>;
}

type ClipboardWithItem = Clipboard & {
  write?: (data: ClipboardItem[]) => Promise<void>;
};

interface ClipboardItemConstructor {
  new (data: AsyncClipboardItemData): ClipboardItem;
}

interface CopyAsyncTextArgs {
  placeholder: string;
  loadText: () => Promise<string>;
}

export async function copyAsyncText({
  placeholder,
  loadText,
}: CopyAsyncTextArgs): Promise<boolean> {
  const clipboard = navigator.clipboard as ClipboardWithItem | undefined;
  if (!clipboard) {
    return false;
  }

  const clipboardItem = globalThis.ClipboardItem as ClipboardItemConstructor | undefined;
  if (clipboard.write && clipboardItem) {
    const textPromise = loadText();
    const blobPromise = textPromise.then((text) => new Blob([text], { type: 'text/plain' }));
    try {
      await clipboard.write([new clipboardItem({ 'text/plain': blobPromise })]);
      return true;
    } catch {
      try {
        await textPromise;
      } catch {
        return false;
      }
    }
  }

  try {
    await clipboard.writeText(placeholder);
    const text = await loadText();
    await clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
