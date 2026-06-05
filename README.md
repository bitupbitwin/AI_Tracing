# AI Tracing

AI Tracing 是一个用于追踪主流 AI 大模型信息的 Python 项目。它会读取配置中的官方来源，抓取模型和价格页面，生成 Markdown 格式的大模型信息报告。

## 当前能力

1. 汇总主流 AI 大模型厂商和模型系列。
2. 记录开源/闭源状态、模型特点、多模态能力、订阅价格、API 价格和优惠信息。
3. 默认输出 Markdown 报告到 `reports/ai_model_report.md`。
4. 保留来源链接和抓取状态，便于人工复核。
5. 可选接入 SerpAPI、Bing Search 或 Tavily 进行更多来源发现。

## 快速开始

```bash
python ai_model_tracing.py
```

生成报告后查看：

```bash
reports/ai_model_report.md
```

如果当前环境不能联网，可以先生成配置版报告：

```bash
python ai_model_tracing.py --no-fetch
```

## 启用搜索发现

脚本默认使用 `data/model_sources.json` 中的官方来源。若要自动发现更多网页，可以配置以下任一环境变量：

```bash
SERPAPI_KEY=your_key
BING_SEARCH_API_KEY=your_key
TAVILY_API_KEY=your_key
```

然后运行：

```bash
python ai_model_tracing.py --discover
```

## 数据源维护

核心配置文件是 `data/model_sources.json`。新增模型时，建议优先填写官方来源：

```json
{
  "name": "Provider Name",
  "sources": ["https://example.com/models"],
  "pricing_sources": ["https://example.com/pricing"],
  "models": [
    {
      "name": "Model Name",
      "openness": "闭源",
      "multimodal": "是",
      "features": "模型特点",
      "api_price_note": "见官方价格页",
      "subscription_price_note": "见官方订阅页"
    }
  ]
}
```

## 输出字段

| 字段 | 说明 |
| --- | --- |
| 厂商 | 模型归属公司或平台 |
| 模型/系列 | 模型名称或模型家族 |
| 开源状态 | 开源、开放权重、闭源或混合 |
| 多模态 | 是否支持图像、音频、视频等能力 |
| 特点 | 模型主要能力和定位 |
| 订阅价格 | 用户侧包月、包年或会员套餐 |
| API/调用价格 | 开发者调用计费 |
| 优惠 | 免费额度、折扣或试用信息 |
| 抓取状态 | 来源抓取是否成功 |
| 来源 | 官方链接或搜索发现链接 |

## 项目计划

完整开发计划见 `docs/PROJECT_PLAN.md`。

## 注意事项

AI 模型价格和订阅政策变化很快，脚本会尽量提取页面中的价格片段，但最终结论必须以来源链接中的官方信息为准。抓取不到价格时，脚本会保留“需查看来源”提示，不会编造价格。
