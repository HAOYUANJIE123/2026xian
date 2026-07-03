# 版本 Tag 说明

每个 tag 对应一次可上传的 `lychee-python-client.zip`，并记录**线上对战**与**已知缺陷**。  
查看 tag 摘要：`git show v4.2-contest-guard`（annotated tag 消息）  
打新 tag：`python tag_release.py v4.x-name`

---

## v4.2-contest-guard（`3db7e66`）— **当前推荐**

### 策略变更

- 窗口争夺输掉后 `WAITING` 不再死等，继续走路线的 `MOVE`
- 在边上遇敌方 guard 时主动 `BREAK_GUARD` / `FORCED_PASS`，不再 passive wait 等 guard 衰减

### 线上对战

| 对手 | 我方 | 对手 | 送达 | 说明 |
|------|------|------|------|------|
| — | — | — | — | **v4.2 尚未上线实测**；上传后请补 replay 到 `log/` |

### 针对 v4.1 已修复的缺陷

| 缺陷 | 表现 | replay 证据 |
|------|------|-------------|
| S07 争夺后卡死 | 输掉 T_010 窗口争夺后 R191–R600 无限 `WAIT`，未送达 | `log/2614/replay (3).txt` |
| S09 边上等 guard | R330–R492 在 S09→S10 等 def6 衰减，无 `BREAK_GUARD`，来不及送达 | `log/2616/replay (2).txt` |

### 待验证（上线后看 replay）

- [ ] 输掉窗口争夺后能否继续前往 S09/S14
- [ ] S09→S10 是否出现 `BREAK_GUARD`
- [ ] 是否有 `DELIVER` / `delivered=true`

---

## v4.1-pack-checks（`74fc4c0`）

### 策略变更

- 策略同 `v4-guard-break`，无新逻辑
- 新增 `pack_checks.py`、`UPLOAD_CHECKLIST.md`，打包前自动跑测试与 ZIP 校验

### 线上对战（策略仍为 v4，缺陷同 v4）

| 对手 | 我方 | 对手 | 送达 | replay |
|------|------|------|------|--------|
| 2614 | 80 | 748 | 否 | `log/2614/replay (3).txt` |
| 2616 | 90 | 719 | 否 | `log/2616/replay (2).txt` |

### 已知缺陷

| 缺陷 | 表现 |
|------|------|
| S07 争夺后卡死 | 输掉窗口争夺后无限 `WAIT`（410 次），只完成 3 任务 |
| S09 边上不破守 | 遇 S10 guard 只 `WAIT` 等衰减，约 160 回合浪费；R600 仍在 S11→S12，未送达 |
| 无 BREAK_GUARD | 整场无主动破守动作 |

---

## v4-guard-break（`729ae42`）

### 策略变更

- 官道路线 S02→S03→S07→…→S15，冰鉴/战马/RUSH_PROTECT
- 新增 `BREAK_GUARD` / `FORCED_PASS`、验关后送货、防回退

### 线上对战

| 对手 | 我方 | 对手 | 送达 | replay |
|------|------|------|------|--------|
| 2616 | 80 | 719 | 否 | `log/2616/replay (1).txt` |

本地自测：约 **761** vs Demo ~458，可送达 R482。

### 已知缺陷（v4.2 前）

| 缺陷 | 表现 |
|------|------|
| 边上遇 guard 只 WAIT | 194× `MOVE_BLOCKED_BY_GUARD`，卡 S09→S10 |
| 窗口争夺后卡死 | 同 v4.1（S07 无限 WAIT） |
| 边上不触发 BREAK_GUARD | `_edge_guard_response` 只返回 WAIT |

### 更早版本（无 tag，水路旧客户端）

| 对手 | 我方 | 对手 | 送达 | replay |
|------|------|------|------|--------|
| 2614 | 684 | 761 | 是 R466 | `log/2614/replay.txt` |

缺陷：3 任务 / 鲜度偏低，官道+任务优化未上线。

---

## 打 tag 规范

```powershell
cd python-client
python pack_submission.py
python tag_release.py v4.3-xxx --recommend
git push origin master
git push origin v4.3-xxx
# 若更新已有 tag 消息：git push --force origin v4.3-xxx
```

`tag_release.py` 会从本文件对应章节生成 annotated tag 消息；**上线后请更新本文件「线上对战」表格再重打 tag**。
