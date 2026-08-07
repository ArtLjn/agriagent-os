"""端到端验证:触发写操作 → 审批弹窗渲染 → 点击批准 → 后续事件渲染完成。"""
import asyncio

from playwright.async_api import async_playwright


async def main() -> None:
    errors: list[str] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"PAGEERROR: {e}"))

        await page.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        await page.wait_for_timeout(500)
        await page.click("#new-conv-btn")
        await page.wait_for_timeout(300)

        await page.fill("#msg-input", "帮我记一笔100元的费用，类别是化肥")
        await page.click("#send-btn")

        # 等审批按钮出现
        for _ in range(15):
            if await page.query_selector(".btn-approve"):
                break
            await page.wait_for_timeout(1000)

        if not await page.query_selector(".btn-approve"):
            print("FAIL: 审批按钮未出现")
            await browser.close()
            return

        print("✓ 审批按钮出现，点击批准")
        await page.click(".btn-approve")

        # 在流式过程中实时抓取 DOM（done 事件后会被 loadConversationMessages 重绘清空）
        live_snapshots: list[str] = []
        for _ in range(20):
            await page.wait_for_timeout(500)
            seen = await page.evaluate(
                """() => {
                    const els = document.querySelectorAll('#chat-main .event');
                    return Array.from(els).map(e =>
                        (e.className.split(' ')[1] || e.className));
                }"""
            )
            live_snapshots.append(",".join(seen))
            if await page.query_selector(".event-done"):
                break

        print("=== 流式过程中事件类型序列（每次抓取）===")
        seen_any: set[str] = set()
        for snap in live_snapshots:
            print("-", snap)
            seen_any.update(snap.split(","))
        print(f"=== 出现过的事件类型合集 ===")
        print("-", ",".join(sorted(seen_any)))

        # 等待 done 事件后的重绘完成
        for _ in range(20):
            done = await page.query_selector(".event-done")
            if done:
                break
            await page.wait_for_timeout(1000)

        html = await page.evaluate(
            """() => {
                const els = document.querySelectorAll('#chat-main .event');
                return Array.from(els).map(e => (e.className.split(' ')[1] || e.className) +
                    ' :: ' + (e.innerText || '').slice(0, 90));
            }"""
        )
        print("=== 聊天区事件 ===")
        for h in html:
            print("-", h)

        # 检查流式过程中是否渲染了关键事件类型（直播期间，非重绘后）
        live_joined = ",".join(seen_any)
        checks = {
            "approval_required": "approval_required" in live_joined,
            "approval_result": "approval_result" in live_joined,
            "action": "action" in live_joined,
            "observation": "observation" in live_joined,
            "final_answer": "final_answer" in live_joined,
            "done": "done" in live_joined,
        }
        print("=== 关键事件检查（流式过程）===")
        ok = True
        for k, v in checks.items():
            print(f"- {k}: {'✓' if v else '✗ MISSING'}")
            ok = ok and v
        print(f"=== 结果: {'PASS' if ok else 'FAIL'} ===")

        if errors:
            print("=== 控制台错误 ===")
            for e in errors:
                print("-", e)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
