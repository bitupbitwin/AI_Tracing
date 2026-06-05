#!/usr/bin/env python3
"""
AI model tracing report generator.

The script builds a Markdown report from curated official sources and optional
search-engine discovery results. It intentionally keeps source URLs in the
output so pricing and subscription claims can be checked again later.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html.parser
import json
import os
import re
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCES = ROOT / "data" / "model_sources.json"
DEFAULT_OUTPUT = ROOT / "reports" / "ai_model_report.md"

USER_AGENT = (
    "AI-Tracing/0.1 (+https://github.com/bitupbitwin/AI_Tracing; "
    "research report generator)"
)

PRICE_PATTERN = re.compile(
    r"(?:(?:USD|US\$|\$|CNY|RMB|¥)\s?\d+(?:\.\d+)?(?:\s?[kKmM])?"
    r"(?:\s*/\s?(?:month|mo|year|yr|1M|1K|token|tokens|百万tokens|千tokens))?)"
)

MONTH_PATTERN = re.compile(r"(\$|US\$|USD|CNY|RMB|¥)\s?\d+(?:\.\d+)?\s*/?\s?(month|mo|月)", re.I)
YEAR_PATTERN = re.compile(r"(\$|US\$|USD|CNY|RMB|¥)\s?\d+(?:\.\d+)?\s*/?\s?(year|yr|年)", re.I)

OPEN_KEYWORDS = (
    "open source",
    "apache 2.0",
    "mit license",
    "weights",
    "开源",
    "开放权重",
)
DISCOUNT_KEYWORDS = (
    "discount",
    "promotion",
    "free trial",
    "free tier",
    "credit",
    "优惠",
    "免费额度",
    "折扣",
)
MULTIMODAL_KEYWORDS = (
    "multimodal",
    "vision",
    "image",
    "audio",
    "video",
    "tool use",
    "多模态",
    "视觉",
    "图像",
    "语音",
    "视频",
)


class TextExtractor(html.parser.HTMLParser):
    """Small dependency-free HTML text extractor."""

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.title_parts: list[str] = []
        self.body_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        clean = " ".join(data.split())
        if not clean or self._skip_depth:
            return
        if self._in_title:
            self.title_parts.append(clean)
        else:
            self.body_parts.append(clean)

    @property
    def title(self) -> str:
        return " ".join(self.title_parts).strip()

    @property
    def body(self) -> str:
        return " ".join(self.body_parts).strip()


@dataclass
class FetchResult:
    url: str
    ok: bool
    title: str = ""
    text: str = ""
    error: str = ""


@dataclass
class ModelRow:
    provider: str
    model: str
    openness: str
    multimodal: str
    features: str
    subscription_price: str
    api_price: str
    discount: str
    source_status: str
    sources: list[str] = field(default_factory=list)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def request_json(url: str, *, method: str = "GET", body: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {"User-Agent": USER_AGENT}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def fetch_url(url: str) -> FetchResult:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=25) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read(1_500_000)
        if "text" not in content_type and "html" not in content_type and not url.endswith(".md"):
            return FetchResult(url=url, ok=False, error=f"unsupported content type: {content_type}")
        html = raw.decode("utf-8", errors="replace")
        parser = TextExtractor()
        parser.feed(html)
        return FetchResult(url=url, ok=True, title=parser.title, text=parser.body)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return FetchResult(url=url, ok=False, error=str(exc))


def unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        value = value.strip()
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def find_keyword_snippets(text: str, keywords: Iterable[str], limit: int = 4) -> list[str]:
    snippets: list[str] = []
    lowered = text.lower()
    for keyword in keywords:
        idx = lowered.find(keyword.lower())
        if idx == -1:
            continue
        start = max(0, idx - 160)
        end = min(len(text), idx + 260)
        snippet = " ".join(text[start:end].split())
        if snippet not in snippets:
            snippets.append(snippet)
        if len(snippets) >= limit:
            break
    return snippets


def extract_prices(text: str) -> list[str]:
    prices = PRICE_PATTERN.findall(text)
    return unique(prices)[:10]


def detect_discount(text: str) -> str:
    snippets = find_keyword_snippets(text, DISCOUNT_KEYWORDS, limit=2)
    if snippets:
        return "发现疑似优惠/免费额度信息：" + " / ".join(shorten(s, 120) for s in snippets)
    return "未发现明确优惠信息"


def infer_multimodal(config_value: str, text: str) -> str:
    if config_value:
        return config_value
    if find_keyword_snippets(text, MULTIMODAL_KEYWORDS, limit=1):
        return "是（页面出现多模态相关描述，需复核）"
    return "未确认"


def infer_openness(config_value: str, text: str) -> str:
    if config_value:
        return config_value
    if find_keyword_snippets(text, OPEN_KEYWORDS, limit=1):
        return "可能开源/开放权重（需复核许可证）"
    return "未确认"


def shorten(value: str, width: int = 140) -> str:
    return textwrap.shorten(" ".join(value.split()), width=width, placeholder="...")


def markdown_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def discover_with_serpapi(query: str, max_results: int) -> list[str]:
    key = os.getenv("SERPAPI_KEY")
    if not key:
        return []
    params = urllib.parse.urlencode({"q": query, "api_key": key, "engine": "google", "num": max_results})
    data = request_json(f"https://serpapi.com/search.json?{params}")
    return [item.get("link", "") for item in data.get("organic_results", [])][:max_results]


def discover_with_bing(query: str, max_results: int) -> list[str]:
    key = os.getenv("BING_SEARCH_API_KEY")
    if not key:
        return []
    params = urllib.parse.urlencode({"q": query, "count": max_results})
    req = urllib.request.Request(
        f"https://api.bing.microsoft.com/v7.0/search?{params}",
        headers={"Ocp-Apim-Subscription-Key": key, "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
    return [item.get("url", "") for item in data.get("webPages", {}).get("value", [])][:max_results]


def discover_with_tavily(query: str, max_results: int) -> list[str]:
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        return []
    data = request_json(
        "https://api.tavily.com/search",
        method="POST",
        body={
            "api_key": key,
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "include_answer": False,
        },
    )
    return [item.get("url", "") for item in data.get("results", [])][:max_results]


def discover_urls(query: str, max_results: int) -> list[str]:
    urls: list[str] = []
    for discover in (discover_with_serpapi, discover_with_bing, discover_with_tavily):
        try:
            urls.extend(discover(query, max_results))
        except Exception as exc:  # noqa: BLE001 - discovery should not block the report.
            print(f"[warn] discovery failed for {query!r}: {exc}")
    return unique(urls)[:max_results]


def build_rows(config: dict[str, Any], *, no_fetch: bool, discover: bool, max_discovered: int) -> list[ModelRow]:
    rows: list[ModelRow] = []
    for provider in config["providers"]:
        provider_name = provider["name"]
        provider_sources = provider.get("sources", [])
        pricing_sources = provider.get("pricing_sources", [])
        for model in provider.get("models", []):
            model_name = model["name"]
            urls = list(provider_sources) + list(pricing_sources) + model.get("sources", [])
            if discover:
                query = f"{provider_name} {model_name} pricing subscription open source multimodal"
                urls.extend(discover_urls(query, max_discovered))
            urls = unique(urls)

            fetches: list[FetchResult] = []
            if not no_fetch:
                fetches = [fetch_url(url) for url in urls]
            combined_text = " ".join(result.text for result in fetches if result.ok)
            prices = extract_prices(combined_text)
            price_text = "；".join(prices) if prices else model.get("api_price_note") or "未从页面自动提取，需查看来源"
            subscription_price = model.get("subscription_price_note") or "未从页面自动提取，需查看来源"
            if combined_text:
                month_hits = [m.group(0) for m in MONTH_PATTERN.finditer(combined_text)]
                year_hits = [m.group(0) for m in YEAR_PATTERN.finditer(combined_text)]
                parts = []
                if month_hits:
                    parts.append("包月：" + "，".join(unique(month_hits)[:4]))
                if year_hits:
                    parts.append("包年：" + "，".join(unique(year_hits)[:4]))
                if parts:
                    subscription_price = "；".join(parts)

            source_status = "未联网抓取，仅使用配置来源" if no_fetch else summarize_fetches(fetches)
            features = model.get("features", "")
            snippets = find_keyword_snippets(combined_text, [model_name, provider_name, "pricing", "价格", "能力"], limit=2)
            if snippets:
                features = shorten((features + "；" if features else "") + " / ".join(snippets), 220)

            rows.append(
                ModelRow(
                    provider=provider_name,
                    model=model_name,
                    openness=infer_openness(model.get("openness", ""), combined_text),
                    multimodal=infer_multimodal(model.get("multimodal", ""), combined_text),
                    features=features or "待补充",
                    subscription_price=subscription_price,
                    api_price=price_text,
                    discount=detect_discount(combined_text) if combined_text else model.get("discount_note", "未联网核验"),
                    source_status=source_status,
                    sources=urls,
                )
            )
    return rows


def summarize_fetches(fetches: list[FetchResult]) -> str:
    if not fetches:
        return "未配置来源"
    ok_count = sum(1 for item in fetches if item.ok)
    if ok_count == len(fetches):
        return f"已抓取 {ok_count}/{len(fetches)} 个来源"
    return f"已抓取 {ok_count}/{len(fetches)} 个来源，部分失败"


def render_report(rows: list[ModelRow], config: dict[str, Any]) -> str:
    generated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# AI 大模型信息追踪报告",
        "",
        f"- 生成时间：{generated}",
        f"- 数据源配置：`{DEFAULT_SOURCES.as_posix()}`",
        "- 说明：价格、订阅和优惠信息变化很快，报告保留来源链接；正式引用前请打开来源复核。",
        "",
        "## 汇总表",
        "",
        "| 厂商 | 模型/系列 | 开源状态 | 多模态 | 特点 | 订阅价格 | API/调用价格 | 优惠 | 抓取状态 | 来源 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        sources = "<br>".join(f"[来源{i + 1}]({url})" for i, url in enumerate(row.sources[:8]))
        lines.append(
            "| "
            + " | ".join(
                markdown_escape(value)
                for value in [
                    row.provider,
                    row.model,
                    row.openness,
                    row.multimodal,
                    row.features,
                    row.subscription_price,
                    row.api_price,
                    row.discount,
                    row.source_status,
                    sources,
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## 后续维护建议",
            "",
            "1. 优先补充官方 pricing、model card、release note 页面，避免引用二手价格。",
            "2. 每次更新后提交生成时间和来源链接，便于追踪历史变化。",
            "3. 对自动发现的新来源进行人工复核，再写入 `data/model_sources.json`。",
            "4. 对开源模型单独复核许可证、权重发布地址和商用限制。",
            "",
            "## 覆盖范围",
            "",
            f"- 当前配置厂商数：{len(config.get('providers', []))}",
            f"- 当前配置模型/系列数：{len(rows)}",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an AI large-model tracing Markdown report.")
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES, help="Path to model source JSON.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Markdown output path.")
    parser.add_argument("--no-fetch", action="store_true", help="Do not fetch web pages; generate from configured metadata only.")
    parser.add_argument("--discover", action="store_true", help="Use optional search APIs to discover extra URLs.")
    parser.add_argument("--max-discovered", type=int, default=3, help="Maximum discovered URLs per model/provider query.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_json(args.sources)
    rows = build_rows(config, no_fetch=args.no_fetch, discover=args.discover, max_discovered=args.max_discovered)
    report = render_report(rows, config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"Generated {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
