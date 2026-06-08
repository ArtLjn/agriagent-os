# 记录 UI Spec

## Image

- Source image: `/Users/ljn/Documents/demo/explore/output/imagegen/mvp-pages/record.png`
- Canvas: `1024x2224px`
- Page: `记录`

## Purpose

MVP 的主要创建入口。AI 帮填和手动填写都免费，且同等可见。

## Required UI

- Top: `记录`, `你说一句，也可以自己填`
- Main choices: `AI帮我填`, `自己填`
- AI input placeholder: `买肥料128.5，记到春季西瓜`
- Input modes: `说话`, `打字`, `拍照`
- Manual actions: `记账`, `记农事`, `记工资`, `建批次`, `新增工人`, `建模板`
- Preview card: `我理解为：记一笔支出`
- Preview values: `复合肥`, `128.5元`, `春季西瓜`, `今天`
- Actions: `改一下`, `保存`
- Bottom nav: `记录` selected.

## Invariants

- 不要技术字段。
- 不要后台表单网格。
- AI 失败时可以进入手动填写。
