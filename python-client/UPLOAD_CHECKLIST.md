# 上传前 Checklist

平台提交文件：仓库根目录 **`lychee-python-client.zip`**（由 `pack_submission.py` 生成）。

## 1. 本地打包（含自动检查）

```powershell
cd python-client
python pack_submission.py
```

默认会依次执行：

1. 源码结构检查（`start.sh`、客户端入口、策略文件等）
2. 单元测试（`tests/`）
3. 生成 ZIP
4. ZIP 结构校验（根目录 `start.sh` 可执行、路径无反斜杠等）

跳过单元测试（仅调试打包时用）：

```powershell
python pack_submission.py --skip-tests
```

## 2. 打包后人工确认

- [ ] ZIP 在 **`2026xian/lychee-python-client.zip`**（与 `python-client/` 同级）
- [ ] 解压后根目录直接有 `start.sh`，不是多套一层文件夹
- [ ] 当前 Git 改动已提交；重要版本已打 tag（如 `v4-guard-break`）

## 3. 上传平台

- [ ] 上传 **`lychee-python-client.zip`**
- [ ] 记录对应 **commit / tag**，方便回滚

## 4. 上线后看 replay（必做）

| 检查项 | 正常 | 异常 |
|--------|------|------|
| 动作不断连 | 每回合有 MOVE/WAIT/… | `CLIENT_TIMEOUT`、整局几乎无动作 |
| 送达 | 有 `DELIVER` / `delivered=true` | 只有 80 分左右、未送达 |
| 对守军型对手 | 出现 `BREAK_GUARD` 或 `FORCED_PASS` | 大量 `MOVE_BLOCKED_BY_GUARD` 且无破守 |
| 任务 | 皇榜任务分 ~170 | 仍 ~125（只做了 3 个任务） |
| 鲜度 | 送达鲜度 ~85+ | 仍 ~74（可能走了水路旧逻辑） |

## 5. 版本对照

| Tag | 要点 |
|-----|------|
| `v4-guard-break` | 破守、验关/送货、官道+冰鉴（策略 v4） |
| **`v4.1-pack-checks`** | **当前推荐**：含 v4 策略 + 打包自动检查 + checklist |

回滚到某一版：

```powershell
git checkout v4-guard-break
cd python-client
python pack_submission.py
```
