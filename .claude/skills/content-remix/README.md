# content-remix

公众号贴图原创创作：读取素材与偏好，独立创作文案和场景，复用当前暂用视觉风格，编译一份完整多图提示词，由用户复制到ChatGPT网页端手动生成整组图片，提示词交付后结束，不要求回传图片、不默认进行图片审核。不自动调用生图接口。

## 安装与依赖

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
bash install.sh all --force
```

安装副本位于项目`.agents/skills/content-remix`和`.claude/skills/content-remix`，修改源文件后同步，重新开会话加载。个人作品、偏好和风格不打包进安装副本。Pillow用于实际生图后的解码及白底处理，离线提示词生成只需Python标准库。

## 项目结构

```text
wechat-posts/日期-主题/
├── 图片/01.png…
├── 发布文案.md
├── 创作提示词.md
├── 创作资料/
│   ├── cards.json
│   ├── 对标分析.md
│   ├── 选题与分镜.md
│   └── 创作约束.md
├── 对标素材/
└── 记录/
    ├── 审核.md
    ├── 发布数据.md
    └── 生成记录.json
```

只支持此目录，不兼容旧路径。当前内容源是`创作资料/cards.json`。过程文件在`.tmp/`，采用成品并更新记录后直接删除，不归档或默认保存版本快照。

## 默认选题原则

贴近对标的同一具体读者需求，不仅是同赛道。默认保留目标读者、表达主体、核心问题、情绪和标题承诺，给出3个贴近原选题的方案；话术、例子、人物动作与画面独立创作。选定前做“去掉标题，是否仍解决同一个具体问题”的检查。仅用户明确要求时拓展新选题；历史去重不自动成为换题理由。选题、形式和原创表达分别评价，素材不足标待评。边界案例见`evals/topic-alignment.md`。

## 当前风格与记忆

工作区`.content-remix/styles/current.json`保存暂用视觉配置和认可证据，角色、主题和台词不写入风格配置。新项目可显式复制style_guide/layout：

```bash
python3 scripts/apply_style.py --project "$PROJECT" --profile .content-remix/styles/current.json
```

复制后由项目JSON独立维护，修改全局配置不会覆盖既有作品。用户本次要求优先。偏好与案例在`.content-remix/`，认可仅适用于明确范围，暂用不等于永久偏好。

## 完整提示词与整组生成

```bash
python3 scripts/ingest.py --url 'https://mp.weixin.qq.com/s/...' --out "$PROJECT"
# 由代理写入内容与分镜，然后：
python3 scripts/build_prompt.py --project "$PROJECT" --contract-only
python3 scripts/build_prompt.py --project "$PROJECT"
```

将`创作提示词.md`完整代码块一次提交给ChatGPT，包括全组设定和每张准确文案。不先试首张、不逐张确认、不逐张生成。返回缺图或拼图则报告未完成，不自动补图或拆拼图。

当前交付止于完整提示词。由用户在ChatGPT网页端手动生成，不调用DDCherry、OpenAI或宿主生图工具。DDCherry本次整组测试即使传n=4也返回单张拼图；相关脚本保留为历史实验，不在当前流程中使用，不推断所有API均不支持多图。

无需配置API或安装Pillow即可编译提示词。提示词交付即完成任务，不把回传或图片审核作为后续待办。默认检查仅针对选题、文案、分镜和提示词；只有用户另行明确请求时才检查图片。已有生成记录仅作为历史事实保留，新提示词项目不要求生成记录。

## 检查与验证

默认只做文本策划和提示词编译检查，不要求实际图片。以下视觉分级仅供用户以后明确请求图片审核时使用，不属于默认交付条件。

- **阻断问题**：缺图、拼图、错字漏字、文件损坏、核心图文矛盾。
- **可接受偏差**：轻微字形、发型或版式变化，须说明证据，由用户决定。
- **尚未验证**：手机实机阅读、素材缺失或发布效果，不能冒充通过。

程序检查不替代视觉审核；整组看图后才交付，不自动发布或修图。

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/evaluate.py --out creative-evaluation.md
.venv/bin/python scripts/quality_check.py --project "$PROJECT"
python3 scripts/project_memory.py sync --workspace "$PWD"
```
