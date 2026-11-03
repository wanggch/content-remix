# content-remix：公众号贴图原创创作 Skill

支持公众号链接、保存的HTML、文字、完整截图和已有风格档案。完成对标分析、原创选题、创作约束、分镜、整组带字图片提示词、发布文案及审核。默认4张独立3:4竖图，按用户要求调整。

## 安装与更新

```bash
cd /path/to/content-remix
bash ./install.sh all
# 修改源文件后更新两个项目内安装副本：
bash ./install.sh all --force
```

`all`可换为`claude`或`codex`。安装目标由调用时的当前目录决定，位于 `.claude/skills/content-remix` 和 `.agents/skills/content-remix`，不写全局目录。`--force`替换安装副本及其中手工修改；修改应在源目录完成。更新后重开相应会话以加载新版。

安装包含运行脚本、参考规则和合成评估案例；用户偏好、选题历史与作品保存在创作工作区，不随Skill安装分发。

## 对话使用

Claude Code：

```text
/content-remix 参考这篇公众号贴图文章，完成原创四图策划：https://mp.weixin.qq.com/s/...
```

Codex：

```text
$content-remix 参考这篇公众号贴图文章，交付创作提示词：https://mp.weixin.qq.com/s/...
```

链接受限时可提供完整截图或本地HTML。截图由当前宿主的视觉能力读取，脚本不执行OCR；无视觉能力时明确未知，不虚构画风。同账号多篇样本可归纳 `style-profile.md`，用户偏好另行记录。

## 当前流程

1. 读取工作区偏好与历史选题，检查候选主题、场景和动作是否重复。
2. 导入素材，区分事实与推测，识别并列卡、连续故事、前后对照或步骤教程。
3. 给出至少5个原创候选并选定一个，在分镜前固定结构、层级、篇幅、语感与视觉五项约束。
4. 在 `cards.json` 维护全组设定、逐图画面和准确文案，脚本生成 `02-创作约束.md` 与唯一提示词文件 `prompts/创作提示词.md`。
5. 复制整组提示词到支持生图的ChatGPT，生成独立带字图片；补齐发布文案和审核记录，更新选题索引。
6. 实际图片收到后再逐张审核，未生图时只报告提示词完成。

人物一致性与场景连续性分别处理：并列卡可跨时空，故事要求因果连续，对照要求条件可比，教程要求步骤完整。脚本不调用语言模型；分析和创作由当前代理执行。

## 常用命令

```bash
SKILL_DIR="/path/to/project/.agents/skills/content-remix"
WORKSPACE="/path/to/project"
PROJECT="$WORKSPACE/wechat-posts/日期-主题"

python3 "$SKILL_DIR/scripts/project_memory.py" context --workspace "$WORKSPACE" --query '本次主题 场景 动作'
python3 "$SKILL_DIR/scripts/ingest.py" --url 'https://mp.weixin.qq.com/s/...' --out "$PROJECT"
# 也可改用 --html '/path/to/article.html'、--text '/path/to/article.md'
# 或 --screenshots '/path/to/01.png' '/path/to/02.png'

# 先由代理按 references/cards-schema.md 写入全组设定和约束，cards可暂为空：
python3 "$SKILL_DIR/scripts/build_prompt.py" --project "$PROJECT" --contract-only
# 完成分镜与cards后统一生成：
python3 "$SKILL_DIR/scripts/build_prompt.py" --project "$PROJECT"
python3 "$SKILL_DIR/scripts/quality_check.py" --project "$PROJECT"
python3 "$SKILL_DIR/scripts/project_memory.py" sync --workspace "$WORKSPACE"
```

JSON为统一内容源，修改后重新生成；检查器会发现整组文件或约束未同步、准确文案缺失、模板占位符、结构字段不符等问题。不会生成或要求 `prompts/01.md` 等文件。不同于文件校验，语感、审美、原创性与实际图片需要另外审查。

## 工作区记录

`.content-remix/preferences.json` 保存明确偏好与推测，每条附证据和适用范围。本次指令优先，明确偏好优先于推测；同类以最新明确要求为准。`.content-remix/topic-history.json` 从现有作品重建，记录主题、结构、场景和动作；删除项目后运行sync清除索引。

```bash
python3 "$SKILL_DIR/scripts/project_memory.py" preference --workspace "$WORKSPACE" \
  --kind explicit --key example_key --value '用户实际要求' \
  --evidence '用户原话及实际来源位置' --scope workspace
```

仅在有真实证据时记录。字面检索只辅助查重，不证明语义重复；建档不等于用户认可或发布成功。具体规则见 `references/workspace-memory.md`。

## 图片生成与审核

默认无需API Key：复制 `创作提示词.md` 中完整代码块到ChatGPT。模型、界面和额度决定单轮输出数量，不能承诺全部一次完成。图片直接带准确中文文案；下载后核对文字、人物、结构和手机阅读效果，保存为 `final/01.png` 等。其他格式需真实转换，不能只改扩展名。无图时不宣称审核通过，不提供定向修图流程。

如用户明确选择OpenAI付费图像API并配置 `OPENAI_API_KEY`：

```bash
python3 "$SKILL_DIR/scripts/render_images.py" --project "$PROJECT"       # 只预览
python3 "$SKILL_DIR/scripts/render_images.py" --project "$PROJECT" --yes # 已获费用授权
```

模型访问与计费取决于账号及官方当前规格，必要时用 `--model` 指定可用模型。脚本从同一JSON即时组合请求，输出到 `generated/`，经检查后选入 `final/`。不默认调用、不自动重试付费请求。

## 验证与创作评估

```bash
python3 -m unittest discover -s tests -v
python3 scripts/evaluate.py --out ./creative-evaluation.md
```

四种结构的固定案例位于 `evals/cases.json`，是合成回归案例。报告区分程序检查和待语义审查，不将自动通过当作用户认可或传播效果证明。随着实际使用，仅在用户明确认可时加入带认可证据的案例；规则见 `references/creative-evaluation.md`。

## 输出目录

```text
wechat-posts/日期-主题/
├── 00-source/
├── 01-analysis.md
├── 02-topics.md
├── 02-创作约束.md
├── 03-storyboard.md
├── cards.json
├── prompts/创作提示词.md
├── 04-publish.md
├── 05-review.md
├── generated/   # 可选API输出
└── final/       # 实际带字图片
```

网页提取可能失败，可换用已保存素材；生图受当前工具、权限与额度限制。结构检查不能代替实际图片、版权或原创性审核。发布由用户自行执行，不提供登录绕过或自动发布。
