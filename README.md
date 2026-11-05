# content-remix

公众号贴图原创创作：读取素材与偏好，独立创作文案和场景，复用当前暂用视觉风格，编译一份完整多图提示词，由用户复制到ChatGPT网页端手动生成整组图片，提示词交付后结束，不要求回传图片、不默认进行图片审核。不自动调用生图接口。

## 安装与依赖

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
bash install.sh all --force
```

安装副本位于项目`.agents/skills/content-remix`（Codex与agy共用）和`.claude/skills/content-remix`。可用`bash install.sh agy --force`仅安装共享副本；`all`只安装共享目录一次，不创建`.agent/`，不写全局目录。修改源文件后同步，重新开会话加载。个人作品、偏好和风格不打包进安装副本。Pillow用于实际生图后的解码及白底处理，离线提示词生成只需Python标准库。

## 项目结构

```text
wechat-posts/日期-主题/
├── 图片/01.png…
├── 发布文案.md
├── 创作提示词.md
├── 创作资料/
│   ├── cards.json
│   ├── 对标引用.json
│   ├── 选题承接.md
│   ├── 选题与分镜.md
│   └── 创作约束.md
└── 记录/
    ├── 审核.md
    ├── 发布数据.md
    └── 生成记录.json
```

只支持此目录，不兼容旧路径。当前内容源是`创作资料/cards.json`。过程文件在`.tmp/`，采用成品并更新记录后直接删除，不归档或默认保存版本快照。

## 默认选题原则

从一个对标演变10个不同主题，按原标题公式拟标题，将原素材、原文拆解和标题方案统一保存于`对标资料/对标主题/`，与原创文章分离。每篇用`创作资料/对标引用.json`引用共享资料（schema_version: 1，reference_path相对文章根目录），不再复制素材。既有本地素材项目仍可检查，不自动迁移已发布记录。既不做同题换皮，也不变成只有赛道关联的泛题。记录原文机制、主题区别及稳定ID；未选标题长期保留，同一对标可以关联多篇独立文章。

## 独立标题策划

按`references/title-strategy.md`执行两道确认：先交标题库并等待选定；标题确认后新建文章并交`创作资料/大纲.md`，等待大纲确认；然后才创作正文、分镜和提示词。正文后只复核标题兑现，不擅自换已确认标题。再次选择库中标题可新建另一篇，不覆盖旧稿。标题不设20字硬限制，不以条数判爱情或保证效果。

## 账号定位入口

工作区`.content-remix/account-profile.md`统一记录受众、内容价值、对标与标题原则、暂用视觉、交付边界及未知项。每次创作前必读；`project_memory.py context`返回全文与available/missing/empty状态。选题前、交付前各完成一次定位核对；标题和大纲需用户确认，普通内部复核不增加额外关卡。不得从正文代词直接推断受众，或从宝妈身份强加育儿叙事。

定位档案只属于当前工作区，不打包进Skill。偏好历史保留，标记`status: superseded`的过时条目不再进入有效上下文；跨key冲突依据明确指令处理，不自动删除证据。

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

将`创作提示词.md`完整代码块一次提交给ChatGPT，包括全组设定和每张准确文案。不先试首张、不逐张确认、不逐张生成。网页端输出数量受模型与界面限制，不把提示词交付声称为实际图片完成；不自动补图或拆拼图，也不默认要求回传检查。

当前交付止于完整提示词。由用户在ChatGPT网页端手动生成，不调用DDCherry、OpenAI或宿主生图工具。DDCherry本次整组测试即使传n=4也返回单张拼图；相关脚本保留为历史实验，不在当前流程中使用，不推断所有API均不支持多图。

无需配置API或安装Pillow即可编译提示词。提示词交付即完成任务，不把回传或图片审核作为后续待办。默认检查仅针对选题、文案、分镜和提示词；只有用户另行明确请求时才检查图片。已有生成记录仅作为历史事实保留，新提示词项目不要求生成记录。

## 检查与验证

默认只做文本策划和提示词编译检查，不要求实际图片。以下视觉分级仅供用户以后明确请求图片审核时使用，不属于默认交付条件。

- **阻断问题**：缺图、拼图、错字漏字、文件损坏、核心图文矛盾。
- **可接受偏差**：轻微字形、发型或版式变化，须说明证据，由用户决定。
- **尚未验证**：手机实机阅读、素材缺失或发布效果，不能冒充通过。

程序检查不替代语义或视觉判断；默认提示词检查完成即交付，不要求看图、回传，不自动发布或修图。只有明确请求图片审核时，才根据实际图片给出审核结论。

`quality_check.py`默认仅检查文本与编译，图片检查需显式加`--check-images`。`apply_style.py`默认只应用画风，覆盖排版需显式加`--include-layout`。新作多文字区使用`text_regions`声明类型、位置和准确文字，不强制气泡在顶、解释在底。

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/evaluate.py --out creative-evaluation.md
.venv/bin/python scripts/quality_check.py --project "$PROJECT"
python3 scripts/project_memory.py sync --workspace "$PWD"
```
