# cards.json：统一创作数据

`schema_version: 2`。人物、画风、版式、逐图画面和准确文案在这里维护。`build_prompt.py` 生成 `创作资料/创作约束.md` 与一份 `创作提示词.md`；不创建逐图提示词文件。API在内存中组合相同数据。

## 字段与示例

以下为单卡数据形状示例，不可直接当作最终作品。默认4张，实际数量以用户需求为准。分镜前可将 `cards` 置为空数组，用 `--contract-only` 生成约束；完整生成及交付检查要求非空数组。

```json
{
  "schema_version": 2,
  "title": "让对方先吃完这顿饭",
  "audience": "共同育儿的成年伴侣",
  "theme": "用接手照护行动留出吃饭时间",
  "content_structure": "parallel",
  "characters": "两位成年伴侣与婴儿，具体外貌与衣服需完整描述",
  "style_guide": "白底家庭卡通、清晰黑线、低饱和暖色块",
  "scene_policy": "并列生活场景，可跨时空；同一人物发型与服装固定",
  "layout": "上部气泡、中部人物、下部解释；文字黑色、清晰、留足安全边距",
  "aspect_ratio": "3:4",
  "scene_tags": ["餐桌", "共同育儿"],
  "action_tags": ["接过婴儿", "坐下吃饭"],
  "format_contract": {
    "structure": {"source": "parallel", "target": "parallel", "evidence": "原文第1—4图各为独立建议"},
    "text_layers": {"source": "气泡＋解释", "target": "气泡＋解释", "evidence": "原文第1图上下文字区"},
    "caption_length": {"source": "观察到单图约80—110字符", "target": "保留相近阅读量", "evidence": "实际读到的气泡和解释", "min_chars": 80, "max_chars": 110},
    "tone": {"source": "口语话术与生活举例", "target": "口语话术与生活举例", "evidence": "原文第2图对话与解释"},
    "visual": {"source": "白底家庭卡通", "target": "白底家庭卡通，新角色与动作", "evidence": "已实际查看的原图"}
  },
  "cards": [
    {
      "index": 1,
      "role": "让照护者安心吃饭",
      "scene": "伴侣站在小餐桌旁稳妥抱起婴儿，另一位坐下继续吃饭；仅画必要餐具，动作与视线自然，文字区不遮挡人物。",
      "bubble_text": "你先吃，我来抱。",
      "body_text": "饭端上桌后，接过孩子，让忙着照护的对方坐下来。",
      "caption": "你先吃，我来抱。\n饭端上桌后，接过孩子，让忙着照护的对方坐下来。",
      "alt": "一位伴侣抱着婴儿，另一位坐在餐桌旁吃饭。"
    }
  ]
}
```

## 数据要求

- `content_structure`：`parallel` / `story` / `contrast` / `tutorial`，不能只靠卡片顺序猜结构。
- `format_contract` 五项均需要 `source`、`target`、`evidence`。结构 source 使用上述枚举或 `unknown`，target 必须与 content_structure 一致；改变结构需写 `change_reason`，引用用户要求。其他维度的主动改动也记录原因，不能把换词当原创。
- 素材缺失的维度用 `source: "unknown"`，evidence 说明缺失原因，target 写本次创作选择；不伪造原文观察。篇幅上下限是本次创作目标，无法观察时明确其为暂定目标。
- `min_chars`、`max_chars` 是含标点与换行的单图完整文案字符数区间。超出仅提示复核，不强制删减长解释。用实际样本确定，避免所有题材套同一字数。
- `scene_policy` 明确哪些要统一、哪些可变；并列卡不强制同一晚或同一房间。连续故事才要求因果与道具连续。对照需写明配对和相同条件，教程需写明步骤依赖。
- `characters`、`style_guide`、`layout` 完整具体且自包含，不写“同上”“见本地文件”。文字排版写明位置、字号层级、字体风格、对比度和安全边距；style_guide 不重复人物、准确文案和整段版式。
- 每张必须含连续整数 `index`、非空 `role`、`scene`、`caption`、`alt`。scene只描述当前画面；caption只保存完整准确入画文字。不保存 `image_prompt`。
- 有气泡和解释时同时填写 `bubble_text`、`body_text`，caption 严格等于两者用一个换行拼接的结果，保留各区原有换行。极简图不必填写这两项。
- 不留模板占位符，不嵌入代码块。脚本保留原始文案，不自行润色、缩句或替换标点。

## 输出

```text
wechat-posts/日期-主题/
├── 对标素材/
├── 创作资料/对标分析.md
├── 创作资料/选题与分镜.md
├── 创作资料/创作约束.md          # 分镜前先固定，由JSON生成
├── 创作资料/cards.json     # 统一内容源
├── 创作提示词.md           # 唯一整组提示词交付文件
├── 发布文案.md
├── 记录/审核.md
├── 记录/生成记录.json
├── .tmp/                  # 整组生成临时文件，采用后删除
└── 图片/                 # 实际带字图片
```

修改文案、人物或画面时先修改JSON，重新运行生成脚本。检查器将生成文件与当前数据完整比较；人为修改或未重新生成都会报告不一致。分镜说明与发布文案的语义一致性仍需审查。
