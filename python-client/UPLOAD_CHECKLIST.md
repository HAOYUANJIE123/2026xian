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
- [ ] 当前 Git 改动已提交；重要版本已打 **annotated tag**（含对战/缺陷说明，见 `VERSION_TAGS.md`）

## 3. 上传平台

- [ ] 上传 **`lychee-python-client.zip`**
- [ ] 记录对应 **commit / tag**（`git show v4.2-contest-guard` 可看对战与缺陷摘要）
- [ ] 上线后把 replay 放进 `log/`，并更新 **`VERSION_TAGS.md`**（对战表 + 原因分析）后重打 tag

## 4. 上线后看 replay（必做）

| 检查项 | 正常 | 异常 |
|--------|------|------|
| 动作不断连 | 每回合有 MOVE/WAIT/… | `CLIENT_TIMEOUT`、整局几乎无动作 |
| 送达 | 有 `DELIVER` / `delivered=true` | 只有 80 分左右、未送达 |
| 对守军型对手 | 出现 `BREAK_GUARD` 或 `FORCED_PASS` | 大量 `MOVE_BLOCKED_BY_GUARD` 且无破守 |
| 任务 | 皇榜任务分 ~170 | 仍 ~125（只做了 3 个任务） |
| 鲜度 | 送达鲜度 ~85+ | 仍 ~74（可能走了水路旧逻辑） |

## 5. 版本对照

完整对战记录、**原因分析**与缺陷见 **`python-client/VERSION_TAGS.md`**。查看 tag：`git show <tag>`。

| Tag | 要点 |
|-----|------|
| `v4-guard-break` | 破守、验关/送货、官道+冰鉴；线上 2616 仍卡 guard |
| `v4.1-pack-checks` | v4 策略 + 打包检查；线上 2614/2616 未送达（S07 卡死、边上不破守） |
| **`v4.2-contest-guard`** | **当前推荐**：修 S07 争夺后卡死 + 边上主动 BREAK_GUARD（待线上验证） |

打 tag（从 `VERSION_TAGS.md` 生成 annotated 消息）：

```powershell
cd python-client
python tag_release.py v4.2-contest-guard --recommend --force
```

回滚到某一版：

```powershell
git checkout v4-guard-break
cd python-client
python pack_submission.py
```
