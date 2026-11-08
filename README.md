# lit-radar · 科研文献查询器

面向膜分离、微塑料和高级氧化研究者的中文文献检索网页。可以按研究方向和期刊分区缩小范围，用关键词或 DOI 定位论文，再收藏待读条目、标记阅读进度。

**[打开在线查询器](https://mhl533.github.io/lit-radar/)** · [报告问题或纠正条目](https://github.com/MHL533/lit-radar/issues)

## 收录范围

截至 2026 年 11 月 8 日，文献库收录 **6,532 条论文记录**，设有 **23 个细分方向**，期刊清单包含 **33 种期刊**。最新条目和期刊清单见 [papers.json](papers.json)。

| 领域 | 研究方向举例 |
| --- | --- |
| 膜分离 | 聚酰胺纳滤膜、催化膜、高熵氧化物催化、机器学习与膜、有机溶剂纳滤、膜污染与清洗 |
| 微塑料 | 微塑料、微塑料机器学习识别、微塑料染色与标记 |
| 高级氧化与催化材料 | 水相与气相高级氧化、单原子与双原子催化、MOF 与 COF 材料 |

## 怎样查一篇论文

以查找**催化膜活化过一硫酸盐（PMS）**的研究为例。

1. 在「领域与方向」中选择「膜分离（我的方向）」，再点「催化膜」。
2. 在搜索框输入 `peroxymonosulfate`。搜索会匹配标题、中文要点、期刊名及缩写、DOI 和作者单位，忽略英文大小写。已知 DOI 时，可以直接粘贴 DOI 编号。
3. 用「上线日期」或「中科院分区」缩小范围。打算稍后阅读的论文可以收藏，读完后点「已读」。下次用「★ 收藏」或「未读」筛选即可。

网页当前使用本机账户模式，收藏和已读状态保存在当前浏览器。自行部署时，如需跨设备同步，可先在自己的 Supabase 项目中执行 [建表脚本](supabase/schema.sql)，再在 [config.js](config.js) 填入项目 URL 和公开的 anon key。

## 数据来源与更新

文献清单保存在 [papers.json](papers.json)。自动补录时，脚本从 Crossref 检索期刊论文，按库内期刊清单和标题规则筛选，再按 DOI 去重。自动补录条目的中文要点留空。上线日期优先采用在线发表日期，缺少完整日期时使用 Crossref 记录创建日期。期刊分区和影响因子取自库内维护的期刊信息。

| GitHub Actions 任务 | 何时运行 | 更新内容 |
| --- | --- | --- |
| [Backfill papers](.github/workflows/backfill.yml) | 手动运行，或将补录配置的变更推送到 `main` | 从 Crossref 补录论文，再通过 OpenAlex 补全作者单位 |
| [Fill author institutions](.github/workflows/enrich.yml) | 每 6 小时、手动运行，或将 `papers.json` 的变更推送到 `main` | 按 DOI 查询 OpenAlex，为缺少单位字段的记录补充作者单位及可获取的通讯作者单位 |

维护者可在 [补录配置](scripts/backfill.json) 中用 `since` 和 `until` 设置 Crossref 记录创建日期的检索区间。聚酰胺纳滤膜、催化膜、高熵氧化物催化和机器学习与膜四个方向另设 `own_until`，用于保留之后由人工整理的文献范围。如需沿用当前日期范围重新补录，可在仓库的 **Actions → Backfill papers → Run workflow** 手动触发。[补录脚本](scripts/backfill.py) · [单位补全脚本](scripts/enrich.py)

## 本地运行

安装 Git 和 Python 3 后，在终端运行以下命令。最后一条命令会在本机启动静态文件服务器。

```bash
git clone https://github.com/MHL533/lit-radar.git
cd lit-radar
python -m http.server 8000 --bind 127.0.0.1
```

在浏览器打开 [本地查询器](http://127.0.0.1:8000/)。如果系统使用 `python3` 命令，请将最后一行的 `python` 换成 `python3`。
