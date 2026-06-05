# AI 大模型信息追踪报告

- 生成时间：2026-06-05 01:49 UTC
- 数据源配置：`I:/developapp/aimodeltracing/data/model_sources.json`
- 说明：价格、订阅和优惠信息变化很快，报告保留来源链接；正式引用前请打开来源复核。

## 汇总表

| 厂商 | 模型/系列 | 开源状态 | 多模态 | 特点 | 订阅价格 | API/调用价格 | 优惠 | 抓取状态 | 来源 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OpenAI | GPT / o-series | 闭源 | 是 | 通用推理、代码、文本、图像和语音等能力；以官方模型页为准。 | 见 ChatGPT pricing | 见 OpenAI API pricing | 未联网核验 | 未联网抓取，仅使用配置来源 | [来源1](https://openai.com/api/pricing/)<br>[来源2](https://platform.openai.com/docs/models)<br>[来源3](https://openai.com/chatgpt/pricing/) |
| Anthropic | Claude | 闭源 | 是 | 强调长上下文、复杂推理、代码和企业安全能力。 | 见 Claude plans | 见 Anthropic pricing | 未联网核验 | 未联网抓取，仅使用配置来源 | [来源1](https://www.anthropic.com/claude)<br>[来源2](https://docs.anthropic.com/en/docs/about-claude/models)<br>[来源3](https://www.anthropic.com/pricing)<br>[来源4](https://docs.anthropic.com/en/docs/about-claude/pricing) |
| Google | Gemini | 闭源 | 是 | 原生多模态，覆盖文本、图像、音频、视频和长上下文场景。 | 见 Google AI plans | 见 Gemini API pricing | 未联网核验 | 未联网抓取，仅使用配置来源 | [来源1](https://ai.google.dev/gemini-api/docs/models)<br>[来源2](https://deepmind.google/models/gemini/)<br>[来源3](https://ai.google.dev/gemini-api/docs/pricing)<br>[来源4](https://one.google.com/about/google-ai-plans/) |
| Meta | Llama | 开放权重/需复核许可证 | 部分型号支持 | 开放权重生态，常用于私有化部署和二次微调。 | 无统一官方订阅价 | 模型权重通常不按 API 收费，托管平台另计 | 未联网核验 | 未联网抓取，仅使用配置来源 | [来源1](https://www.llama.com/models/)<br>[来源2](https://github.com/meta-llama)<br>[来源3](https://www.llama.com/llama-downloads/) |
| Mistral AI | Mistral / Mixtral / Magistral | 开源与闭源并存 | 部分型号支持 | 欧洲 AI 厂商，覆盖开放模型、企业模型和推理模型。 | 以官方产品页为准 | 见 Mistral platform pricing | 未联网核验 | 未联网抓取，仅使用配置来源 | [来源1](https://mistral.ai/technology/)<br>[来源2](https://docs.mistral.ai/getting-started/models/)<br>[来源3](https://docs.mistral.ai/platform/pricing/) |
| xAI | Grok | 闭源为主，部分旧模型开放权重需复核 | 部分型号支持 | 强调实时信息、推理和 X 生态接入。 | 见 Grok/X subscription 页面 | 见 xAI API pricing | 未联网核验 | 未联网抓取，仅使用配置来源 | [来源1](https://docs.x.ai/docs/models)<br>[来源2](https://docs.x.ai/docs/pricing)<br>[来源3](https://x.ai/grok) |
| DeepSeek | DeepSeek | 开源与闭源服务并存 | 以官方模型页为准 | 强调高性价比推理、代码和通用对话能力。 | 以官方应用/平台为准 | 见 DeepSeek API pricing | 未联网核验 | 未联网抓取，仅使用配置来源 | [来源1](https://api-docs.deepseek.com/)<br>[来源2](https://github.com/deepseek-ai)<br>[来源3](https://api-docs.deepseek.com/quick_start/pricing) |
| Alibaba Cloud | Qwen / 通义千问 | 开源与闭源服务并存 | 部分型号支持 | 覆盖文本、代码、视觉、音频、多模态和 Agent 场景。 | 以通义/阿里云官方页面为准 | 见阿里云百炼/DashScope 计费文档 | 未联网核验 | 未联网抓取，仅使用配置来源 | [来源1](https://qwenlm.github.io/)<br>[来源2](https://github.com/QwenLM)<br>[来源3](https://help.aliyun.com/zh/model-studio/billing-for-dashscope) |
| Moonshot AI | Kimi / Moonshot | 闭源 | 部分型号支持 | 强调长上下文、中文体验和办公阅读场景。 | 以 Kimi 官方页面为准 | 见 Moonshot platform pricing | 未联网核验 | 未联网抓取，仅使用配置来源 | [来源1](https://platform.moonshot.cn/docs/)<br>[来源2](https://platform.moonshot.cn/docs/pricing/chat) |
| Zhipu AI | GLM / 智谱清言 | 开源与闭源服务并存 | 部分型号支持 | 覆盖通用对话、代码、视觉、视频理解等场景。 | 以智谱官方页面为准 | 见 BigModel pricing | 未联网核验 | 未联网抓取，仅使用配置来源 | [来源1](https://open.bigmodel.cn/dev/api/normal-model/glm-4)<br>[来源2](https://open.bigmodel.cn/pricing) |
| Baidu | ERNIE / 文心 | 闭源为主 | 部分型号支持 | 百度生态模型，覆盖搜索、办公、企业智能体和多模态场景。 | 以文心一言/百度官方页面为准 | 见百度智能云千帆计费文档 | 未联网核验 | 未联网抓取，仅使用配置来源 | [来源1](https://cloud.baidu.com/product/wenxinworkshop)<br>[来源2](https://yiyan.baidu.com/)<br>[来源3](https://cloud.baidu.com/doc/WENXINWORKSHOP/s/Ilkkrb0i5) |
| ByteDance | Doubao / 豆包 | 闭源 | 部分型号支持 | 覆盖文本、视觉、语音、视频和企业智能应用。 | 以豆包官方页面为准 | 见火山引擎豆包计费页面 | 未联网核验 | 未联网抓取，仅使用配置来源 | [来源1](https://www.volcengine.com/product/doubao)<br>[来源2](https://www.volcengine.com/pricing?product=doubao) |
| Tencent Cloud | Hunyuan / 混元 | 开源与闭源服务并存 | 部分型号支持 | 覆盖文本、图像、视频、3D 和企业应用场景。 | 以腾讯元宝/腾讯云官方页面为准 | 见腾讯云混元计费页面 | 未联网核验 | 未联网抓取，仅使用配置来源 | [来源1](https://cloud.tencent.com/product/hunyuan)<br>[来源2](https://cloud.tencent.com/product/hunyuan/pricing) |
| MiniMax | MiniMax / abab / Talkie | 闭源 | 部分型号支持 | 覆盖文本、语音、视频和角色对话等产品形态。 | 以 MiniMax 官方页面为准 | 见 MiniMax platform pricing | 未联网核验 | 未联网抓取，仅使用配置来源 | [来源1](https://www.minimax.io/platform)<br>[来源2](https://platform.minimaxi.com/document)<br>[来源3](https://platform.minimaxi.com/document/Price) |
| Cohere | Command / Embed / Rerank | 闭源 | 以官方模型页为准 | 面向企业检索增强、嵌入、重排和生成式 AI 工作流。 | 以 Cohere pricing 为准 | 见 Cohere pricing | 未联网核验 | 未联网抓取，仅使用配置来源 | [来源1](https://docs.cohere.com/docs/models)<br>[来源2](https://cohere.com/pricing) |

## 后续维护建议

1. 优先补充官方 pricing、model card、release note 页面，避免引用二手价格。
2. 每次更新后提交生成时间和来源链接，便于追踪历史变化。
3. 对自动发现的新来源进行人工复核，再写入 `data/model_sources.json`。
4. 对开源模型单独复核许可证、权重发布地址和商用限制。

## 覆盖范围

- 当前配置厂商数：15
- 当前配置模型/系列数：15
