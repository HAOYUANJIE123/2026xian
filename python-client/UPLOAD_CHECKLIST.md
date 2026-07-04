# 上传前 Checklist

**不要反复上线试错。** 改完策略后由 agent **自动**在本机跑：

```powershell
cd python-client
python validate_before_upload.py --pack
```

通过才会生成 `lychee-python-client.zip`。你只需在 agent 报告「全过」后上传 zip，**不必自己跑命令**。

## 这条命令会做什么

| 步骤 | 内容 | 不过则停 |
|------|------|----------|
| 1 | 源码结构 | ✓ |
| 2 | 单元测试 | ✓ |
| 3 | **2614/2616 replay 回归**（用新策略重放，抓 CLAIM 空转、S09 卡死、边上 MOVE spam） | ✓ |
| 4 | **本地 Demo 对战**（无 UI，headless，要求送达 + 总分≥700） | ✓ |
| 5 | 打 zip（加 `--pack` 时） | ✓ |

缺 opponent replay 文件会直接失败。当前必跑：

- `log/2614/replay (12).txt`、`replay (15).txt`、`replay (17).txt`（2614 742 胜局基准）
- `log/2616/replay (11).txt`、`replay (14).txt`、`replay (16).txt`（2616 胜局基准）

跳过本地对战（仅调试，**不要上传**）：

```powershell
python validate_before_upload.py --skip-local-match
```

## 你不需要再做的事

- ~~改完策略直接 zip 上传~~
- ~~靠 2614/2616 线上对战当第一轮测试~~

线上对战只用于：**验证通过门槛后的微调**（对手新套路），不是抓「CLAIM 173 次空转」这种低级 bug。

## 上线后（仅当本地全过仍异常时）

1. 把 replay 放进 `log/`
2. 再跑 `python validate_before_upload.py --pack`
3. 更新 `VERSION_TAGS.md` 后打 tag

## 常见失败含义

| 失败信息 | 含义 |
|----------|------|
| `repeats identical CLAIM_TASK` | 领任务被拒仍每帧重试 → 会 60 分卡死 |
| `S09 IDLE ... without MOVE` | 关隘空站 |
| `local match score < 700` | Demo 都跑不通，线上更不行 |
| `not delivered` | 未送达，上限 ~80–90 分 |

## 版本记录

见 **`VERSION_TAGS.md`**。打 tag：`python tag_release.py <tag> --recommend --force`
