# content-remix —— 公众号贴图文章原创创作 Skill

适用于 macOS 上的 **Claude Code** 与 **Codex CLI**。输入一篇或多篇公众号文章链接、保存的 HTML、正文，或完整长截图，由 AI 负责对标拆解、原创选题、4 图分镜和提示词，并进行发布前审核。

## 1. 项目内安装（不安装到全局）

先进入需要使用此 Skill 的项目目录，再通过脚本的实际路径运行安装：

```bash
cd "/Users/qianjian/wgc/06-workspace/02-ddcherry-dream/01-code/content-remix"
bash "/Users/qianjian/wgc/06-workspace/02-ddcherry-dream/01-code/content-remix/install.sh" all
```

安装到**当前工作目录**下的 `.claude/skills/content-remix` 和 `.agents/skills/content-remix`，不会写入用户主目录的全局 Skill 路径。请在该项目目录启动 Claude Code / Codex 使用。也可将 `all` 换成 `claude` 或 `codex`，仅安装到对应环境。安装不会主动覆盖已存在的同名 Skill，更新时请加 `--force`。

### 更新已安装的 Skill

修改本项目根目录中的 `SKILL.md`、`scripts/` 或 `references/` 等源文件后，重新运行安装脚本并加上 `--force`，将修改同步到项目内的安装副本：

```bash
cd "/Users/qianjian/wgc/06-workspace/02-ddcherry-dream/01-code/content-remix"
bash ./install.sh all --force
```

也可以只更新一个环境：

```bash
bash ./install.sh claude --force
# 或
bash ./install.sh codex --force
```

注意：

- 安装目标由运行命令时的**当前工作目录**决定；上述命令只更新本项目的 `.claude/skills/content-remix` 和 `.agents/skills/content-remix`，不会写入全局目录。
- `--force` 会删除旧安装副本后重新复制，副本内的手动修改和 `.venv` 也会被删除。请修改项目根目录中的源文件，不要直接修改安装副本；如果此前创建过虚拟环境且仍需使用，更新后需自行重新创建；默认 ChatGPT 生图流程不需要本地虚拟环境。
- 更新后重新启动该项目的 Claude Code / Codex 会话，确保加载新版 Skill。

## 2. 对话中直接使用

**Claude Code**：

```text
/content-remix 参考这篇公众号贴图文章，完成对标拆解和原创四图策划： https://mp.weixin.qq.com/s/jr85nWkTuOiNtJ0vf4PgOw
```

**Codex CLI**：

```text
$content-remix 参考这篇公众号贴图文章，输出完整的原创四图文章： https://mp.weixin.qq.com/s/jr85nWkTuOiNtJ0vf4PgOw
```

提示：先在终端启动 Claude Code / Codex，再在其对话框粘贴对应文本。若新装 Skill 未显示，重开 CLI 会话。

## 3. 公众号访问失败时

微信可能返回反爬/验证码/不完整图片。此时用浏览器手动保存网页 HTML（建议“网页，完整”），或将**完整长截图**按顺序保存成本地文件后输入：

```text
/content-remix 用以下截图作为对标素材：/Users/me/Desktop/article-01.png /Users/me/Desktop/article-02.png；输出一套独立原创的四图内容。
```

截图模式不进行 OCR：需要 Claude Code / Codex 当前可用的视觉能力确实读取图片后才能分析；否则 AI 会要求补充文字或标注未知。

**账号风格档案**：如果提供同一账号的多篇素材，可要求 AI 顺便保存 `style-profile.md`，今后让 Skill 读取该文件，就能复用选题/视觉规律，无需每次从零拆解。单篇文章只能形成临时画像，不宜声称代表整个账号风格。

## 4. 纯脚本使用（可在任何目录运行）

```bash
# 指向已安装 Skill 的项目绝对路径；Codex 用户改为 .agents/skills/content-remix
SKILL_DIR="/Users/qianjian/wgc/06-workspace/02-ddcherry-dream/01-code/content-remix/.claude/skills/content-remix"
python3 "$SKILL_DIR/scripts/ingest.py" --url 'https://mp.weixin.qq.com/s/jr85nWkTuOiNtJ0vf4PgOw' --out './wechat-posts/demo'
```

脚本仅负责采集与整理，并不调用语言模型。文章分析、选题、分镜和文案由你正在运行的 Claude Code / Codex 按 `SKILL.md` 完成。

## 5. 先交付提示词，再用 ChatGPT 生成带字图片

1. Skill 完成必要分析和分镜后，优先输出 `prompts/chatgpt-batch.md`，提供整组图片创作提示词；随后补齐 `cards.json`、逐张提示词与其他文档。
2. 将文件中的总提示词整段复制到支持图片生成的 ChatGPT 对话，一次请求生成多张**独立带字竖图**，不是一张四宫格。文字内容、位置和排版已写入提示词，不需要生成或保留无字版本，也不需要后期叠字。
3. 实际生成数量取决于当前模型、界面和额度；若数量不足或某张有问题，使用文件中的续生成/单张修订指令补齐。
4. 下载后按序保存为 `final/01.png` 等，逐张核对中文错漏、人物一致性和手机端可读性。其他格式需真实转换为 PNG，不能只改扩展名。未收到图片前，只报告“提示词包完成，图片待生成/待审核”。

此流程无需配置 API Key，ChatGPT 权限与额度以账号界面为准。不会默认调用付费 API。`compose_cards.py` 仅作为历史辅助脚本保留，不参与当前流程。

如明确选择通过 OpenAI 图像 API 在终端出图，可使用现有脚本（按带字提示词生成到 `generated/`，选定图片再复制到 `final/`，不再叠字）：

```bash
# 先自己配置 API Key（不要发给对话或写进仓库）
export OPENAI_API_KEY='你的API密钥'
python3 "$SKILL_DIR/scripts/render_images.py" --project './wechat-posts/demo'           # 只预览，不调用 API
python3 "$SKILL_DIR/scripts/render_images.py" --project './wechat-posts/demo' --yes     # 会产生 API 费用
```

默认模型 `gpt-image-2.5-flare`。API 计费和是否能访问取决于你的账号与当前官方政策。多图生成仅通过提示词尽量保持角色一致；要求严格一致时应使用支持参考图的编辑工作流。

图片完成后可运行结构检查，无需 Pillow：

```bash
python3 "$SKILL_DIR/scripts/quality_check.py" --project './wechat-posts/demo'
```

结构检查不能识别中文错字、视觉畸形或原创性问题，仍需实际查看每张图片。

## 6. 输出约定

每次独立新建一个 `wechat-posts/<日期-主题>/`，保存 `00-source`、`01-analysis.md`、`02-topics.md`、`03-storyboard.md`、`cards.json`、`prompts/`、`04-publish.md`、`05-review.md`，优先交付 `prompts/chatgpt-batch.md`；ChatGPT 生成的带字图片保存到 `final/`，`generated/` 仅供可选 API 工作流使用。

## 7. 已知边界

- **网址提取并非百分之百成功**：动态加载、微信安全验证和访问限制可能导致失败，转截图或 HTML 即可继续。
- **无法仅靠脚本自动完成 AI 语义分析**：需要在 Claude Code / Codex 中调用 Skill。
- **Claude Code / Codex 不一定内置图片生成**：无生图工具时交付完整可复制提示词；可选 API 方式会产生费用。
- **AI 视觉审核不是生产级保证**：最终发布前人工预览、确认原创与授权。
- 不提供绕过平台登录、验证码、防爬或自动发布功能。
