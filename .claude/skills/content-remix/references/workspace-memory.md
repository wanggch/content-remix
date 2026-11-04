# 工作区偏好与历史选题

## 存放与优先级

数据存于用户工作区的 `.content-remix/`，不放进安装的Skill目录，不跨工作区读取个人偏好。优先级为：本次用户指令 → 同范围最新explicit明确偏好 → inferred推测。保留原记录和证据，不把推测升级为明确要求。

- `account-profile.md`：当前账号定位入口；区分已确认、当前采用、尚未确认，保存受众、价值、内容边界、标题、视觉与交付规则。创作前必读，context返回完整文本；缺失或空文件明确报告，不编造。个人档案不随Skill安装分发。
- `preferences.json`：版本1，entries数组；每项含kind、key、value、evidence、scope。可选status为active或superseded，省略时视为active。过时记录保留原证据、标superseded并说明替代原因，不参与有效偏好输出。
- `topic-history.json`：从当前 `wechat-posts/*/创作资料/cards.json` 重建的选题索引，含主题、结构、具体场景、动作与项目路径。
- 索引只说明策划曾存在，不等于用户认可、成功发布或运营效果好。删除项目后重新sync会清除对应索引，不复活失败作品。

## 创作前读取

```bash
python3 "$SKILL_DIR/scripts/project_memory.py" context --workspace "$WORKSPACE" --query '候选主题 具体场景 关键动作'
```

继续已有项目时，可加 `--exclude-project 'wechat-posts/日期-主题'` 排除自身。查询输出按字面重合数量排列，最多10项；无匹配也会返回部分历史供检查。记录多时对不同候选分别查询，不能将字面检索当完整语义去重。

在 `创作资料/选题与分镜.md` 附简短历史检查：相近项目、重合主题/场景/动作、新切入点与选题理由。不同标题但相同观点、动作也可能重复；同场景处理不同读者难题则可成立，应说明区别。

## 记录偏好

```bash
python3 "$SKILL_DIR/scripts/project_memory.py" preference --workspace "$WORKSPACE" \
  --kind explicit --key language_style --value '口语、具体生活细节' \
  --evidence '用户本次明确要求的原话及会话或文件位置' --scope workspace
```

证据必须实际存在，不能把示例作为用户事实。用户已明确表达时直接记录，无需再询问。只涉及某账号或项目时将scope写为 `account:账号名` 或 `project:相对路径`，不要泛化成工作区永久偏好。脚本先过滤superseded，再按scope和key选择有效记录，代理只应用本任务相关范围。不同key的冲突不能靠最新同key规则自动解决，需要依据明确指令标记旧记录失效。更新长期定位时同步account-profile.md；只针对某篇的例外不要升级为永久定位。

推测使用 `--kind inferred`，例如从数次修改观察到的倾向，说明观察样本；一次选题不能证明长期题材偏好。出现相反的明确要求时以明确要求为准。记录文件不得保存密钥、登录凭证或不必要的个人信息。

## 定位核对

选题前与交付前都在既有选题与分镜文件简记：读者、代入目的、对标任务、额外叙事、标题/代词/场景/情绪一致性、形式与交付边界。未知账号名称、年龄、商业目标或题材比例不自行补齐，不为完善档案反复询问无关问题。仅用户明确的变化可以更新已确认项。

## 更新索引

```bash
python3 "$SKILL_DIR/scripts/project_memory.py" sync --workspace "$WORKSPACE"
```

交付后和删除项目后执行。sync不修改已有偏好；无偏好文件时创建空记录。项目数据非法时停止更新并报错，避免悄悄覆盖有效索引。新偏好通过preference命令或保持同一结构编辑，不能把自动索引内容当明确偏好。
