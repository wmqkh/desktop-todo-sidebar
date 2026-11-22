# 给「任何 AI / 任何脚本」的接入说明

这份文件是给**别的 AI 助手**看的。如果你（AI）被要求"帮某人管这个看板"或"验收他的待办"，读完这一页就能干活，不需要读源码。

看板本身不判断对错，它只提供两件事：**内容文件**和**验收回执**。所有交互都是读写这个目录下的 JSON / JSONL 文件。

---

## 0. 你可能是两种角色

| 角色 | 干什么 | 读 | 写 |
|---|---|---|---|
| **规划方 planner** | 看用户的项目，给他排今天/本周的任务 | `tasks.json`、项目本身 | `tasks.json` |
| **验收方 verifier** | 用户勾了任务，你核对成果，判 pass / fail | `verify-queue.jsonl`、`成果/` | `verify-result.jsonl` |

两种角色都**不要**碰 `ui.json` 和 `state.json`——那是程序自己的状态，改了会错乱。

---

## 1. tasks.json（内容）

```json
{
  "meta": {
    "balance": 7,            // 可选，任意数字，程序只用来显示
    "total": 10,             // 可选
    "week": "W1（11/23–11/29）"   // 本周标题
  },
  "week": [
    { "id": "w1", "text": "本周任务", "check": "可选：什么算完成" }
  ],
  "days": [
    {
      "date": "2026-11-23",        // 必须是 YYYY-MM-DD，用来建成果目录
      "label": "周一",              // 任意短标签
      "items": [
        {
          "id": "1123-1",           // 全局唯一，稳定，不要复用
          "text": "今天要做什么",
          "art": "该放什么证据（可选，会写进成果目录的提示文件）",
          "check": "验收标准（可选，verifier 优先按它判）"
        }
      ]
    }
  ]
}
```

规则：

- `id` 一旦分配就**不要改**（勾选状态、成果目录都用它当键）。新 id 建议 `YYYYMMDD-N`。
- `days` 按时间顺序排列；程序用 `ui.json` 里的 `dayIndex` 指当前天。
- 可以只写 `text`，其他字段全可选。
- **写完请原子落盘**：先写 `tasks.json.tmp` 再 `os.replace()` 成 `tasks.json`。看板每 1.2 秒轮询一次，直接覆盖写有可能让它读到半个文件（程序会保留上一份好数据并重试，但你白写一次）。

## 2. verify-queue.jsonl（提交队列，程序写，你只读）

每行一个 JSON：

```json
{"id":"1123-1","scope":"today","text":"…","dir":"…/成果/2026-11-23/1123-1","ts":1763890000.1}
```

`dir` 就是用户该放证据的目录。`ts` 是提交时间。

## 3. verify-result.jsonl（验收回执，你写）

每行一个 JSON，**追加**即可：

```json
{"id":"1123-1","verdict":"pass","reason":""}
{"id":"1123-1","verdict":"fail","reason":"仓库里没有 commit"}
```

- 只会匹配处于"已提交（pending）"的项；重复写会被忽略。
- 不想手写 JSON 就用现成脚本：

```bash
python tools/make_result.py --queue                    # 看看有什么待验收
python tools/make_result.py 1123-1 pass
python tools/make_result.py 1123-1 fail "没有截图"
```

---

## 4. 怎么判（重要）

1. 有 `check` 字段 → **以它为准**。
2. 没有 → 看 `text` 要求的东西，去 `dir` 里找证据，必要时看外部来源（GitHub、链接、日志）。
3. **默认从严**：找不到明确证据就 `fail`，并把缺什么写进 `reason`（用户会看到红字提示）。不要因为"他大概做了"就 pass——这是这个工具唯一的意义。
4. `reason` 要写成**可执行的一句**：写"仓库没有 commit"，不要写"还需努力"。

## 5. 给用户的交接话术（可复制）

> 这个目录是一个待办看板。你的任务是当验收方：读 `verify-queue.jsonl` 里未验收的条目，按 `docs/AGENT.md` 的规则核对 `成果/` 目录和外部证据（如 GitHub），然后用 `python tools/make_result.py <id> pass|fail "原因"` 写回结论。

---

## 6. 边界

- 不要修改 `成果/` 里的用户文件（只读）。
- 不要修改 `ui.json` / `state.json`。
- 不要删除 `verify-queue.jsonl` 的历史行（看板按行数增量应用结果）。
- 判定要留痕：每一次 `fail` 都写清楚"缺什么"，让用户能立刻补。
