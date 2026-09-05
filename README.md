# FreeEgg Radar · 赛博鸡蛋自动化情报站

自动抓取各大 AI 厂商的免费 Token / 积分 / API 额度，自动评分排序、自动更新、过期自动下榜。
**零成本**：GitHub Actions（云端定时）+ EdgeOne Pages（腾讯云免费托管，免备案）+ 硅基流动免费模型（可选 AI 解析）。

```
抓取（定时） → 自动评分（蛋力分公式） → 生成 JSON → 提交回仓库 → EdgeOne Pages 自动部署 → 手机/电脑随时看
```

## 一键部署（约 20 分钟）

### 第一步：注册托管（推荐 EdgeOne Pages，零配置）

**方案 A：EdgeOne Pages（推荐，免备案 + 免费长期）**
1. 打开 https://console.cloud.tencent.com/edgeone/pages 注册并实名（腾讯云账号）
2. 首次进入按提示一键开通 Pages（免费版：项目 40 个、构建 500 次/月、静态流量不限量）
3. 控制台 → 创建项目 → **绑定你的 GitHub 仓库** `free-egg-radar` → 部署分支选 `main`
4. 部署完成后记下平台给的访问域名（形如 `xxx.edgeone.app`）

> 免费版**不需要备案**：内容缓存在边缘节点，域名直接可用。

**方案 B：七牛云 Kodo（10GB 存储永久免费，备选）**
1. 打开 https://www.qiniu.com 注册 + 实名认证
2. 控制台 → 对象存储 Kodo → 新建空间（Bucket），访问控制选「公开」
3. 记下测试域名（形如 `xxx.qiniudns.com`），并在仓库 Secrets 配 `QINIU_AK / QINIU_SK / QINIU_BUCKET`
4. 若用七牛，把下方 workflow 里 `python run.py --dry-run` 改为 `python run.py --upload`

### 第二步：建 GitHub 仓库并推送

1. 新建仓库（Public/Private 均可），比如 `free-egg-radar`
2. 把本目录所有文件推上去：

```bash
git init
git add .
git commit -m "init"
git remote add origin https://github.com/<你的用户名>/free-egg-radar.git
git push -u origin main
```

3. （可选）仓库 **Settings → Secrets and variables → Actions** 新增 `SILICONFLOW_API_KEY` = 硅基流动 API Key，用于 LLM 解析增强；不配则系统照常运行

### 第三步：首次手动触发

打开仓库 **Actions** 页 → 左侧「每日自动更新」→ **Run workflow** 手动跑一次。
跑完等 1-2 分钟，EdgeOne Pages 会自动构建部署，访问它的域名即可。

之后每天 08:00 / 20:00（北京时间）自动抓取更新，无需再管。

> Gitee Pages 已于 2024 年停服，无法使用；EdgeOne Pages 是替代它的国内免费托管（免备案）。

## 本地运行（不想用云也行）

```bash
pip install -r requirements.txt
python run.py --dry-run      # 本地生成 site/data/，然后：
cd site && python -m http.server 8899   # 浏览器打开 http://127.0.0.1:8899 预览
python run.py --no-fetch     # 完全离线，只用种子数据
python run.py --upload       # 本地跑完直接上传到配置的存储（七牛/COS）
```

Windows 上想完全本地自动化：任务计划程序 → 创建基本任务 → 每天 → 程序填 `python`，参数填 `C:\...\free-egg-radar\run.py --upload`。

## 架构

```
数据源（官方公开页面/API）
   │  定时抓取（GitHub Actions cron，云端执行与国内访问无关）
   ▼
抓取器  openrouter（官方 API，免费模型池）
         siliconflow（官方定价页，免费模型）
   │
   ▼
评分引擎  蛋力分 = 额度量级40% + 长期性20% + 门槛15% + 时效15% + 来源可信10%
   │
   ▼
生成器   site/data/eggs.json + meta.json
   │
   ▼
发布     EdgeOne Pages（推荐，GitHub push 自动部署，免备案国内加速）
         └ 备选：七牛云 Kodo（对象存储上传）/ 腾讯云 COS
   │
   ▼
静态站点  FreeEgg Radar（手机/电脑直接访问）
```

## 目录结构

```
free-egg-radar/
├── run.py                  # 主流程
├── config.yaml             # 评分权重 / 源开关 / 上传目标
├── core/                   # 模型、评分、合并去重、导出
├── scrapers/               # 抓取器（每个源一个文件，可扩展）
├── llm/                    # 硅基流动免费模型解析（可选）
├── uploaders/              # 七牛云 / 腾讯云 COS 上传
├── data/seeds.json         # 初始种子库（28 条，保证首日有内容）
├── site/                   # 静态前端（深色赛博风格）
└── .github/workflows/      # 每日自动更新（push 触发 EdgeOne Pages 部署）
```

## 扩展新数据源（30 分钟学会）

在 `scrapers/` 新建一个文件，继承 `BaseScraper`，实现 `scrape()` 返回 `list[Egg]`，
然后在 `config.yaml` 的 `sources` 里加一行开关即可。抓取遵守低频率、只抓公开页面。

## 重要说明

- 所有福利信息来自厂商**官方公开页面**，自动条目未人工实测，以官方页面为准
- 抓取器带频率控制（间隔 2 秒+），不绕过反爬、不采集登录后内容
- 蛋力分是"自动评分"，不是厂商官方排序
- EdgeOne Pages 免费版构建次数 500 次/月，本项目每天 2 次只占约 60 次，绰绰有余
- 如需长期稳定，建议以后绑定自己的备案域名；个人小站用平台域名即可
