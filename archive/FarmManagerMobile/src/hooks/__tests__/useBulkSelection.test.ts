import { act, renderHook } from "@testing-library/react-native";
import { useBulkSelection } from "../useBulkSelection";

describe("useBulkSelection", () => {
  it("长按条目后进入选择态并选中该条目", () => {
    const { result } = renderHook(() => useBulkSelection<number>());

    act(() => {
      result.current.beginSelection(3);
    });

    expect(result.current.isSelecting).toBe(true);
    expect(result.current.selectedIds).toEqual([3]);
    expect(result.current.isSelected(3)).toBe(true);
  });

  it("选择态下点击条目会切换选中状态", () => {
    const { result } = renderHook(() => useBulkSelection<number>());

    act(() => {
      result.current.beginSelection(3);
      result.current.toggleSelection(4);
    });

    expect(result.current.selectedIds).toEqual([3, 4]);

    act(() => {
      result.current.toggleSelection(3);
    });

    expect(result.current.selectedIds).toEqual([4]);
  });

  it("最后一个选中项被取消时退出选择态", () => {
    const { result } = renderHook(() => useBulkSelection<number>());

    act(() => {
      result.current.beginSelection(3);
      result.current.toggleSelection(3);
    });

    expect(result.current.isSelecting).toBe(false);
    expect(result.current.selectedIds).toEqual([]);
  });

  it("clearSelection 会清空选择态", () => {
    const { result } = renderHook(() => useBulkSelection<number>());

    act(() => {
      result.current.beginSelection(3);
      result.current.toggleSelection(4);
      result.current.clearSelection();
    });

    expect(result.current.isSelecting).toBe(false);
    expect(result.current.selectedIds).toEqual([]);
  });
});
