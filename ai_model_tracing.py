#!/usr/bin/env python3
"""
AI model tracing report generator.

The script builds an interactive HTML dashboard from curated official sources,
local ranking files, and optional search-engine discovery results. It preserves
source URLs and fetch statuses for validation.
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
DEFAULT_OUTPUT = ROOT / "reports" / "ai_model_report.html"

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

DOMESTIC_PROVIDERS = {
    # 中文厂商名（数据库展示用）
    "深度求索", "阿里云", "月之暗面", "智谱ai", "百度",
    "字节跳动", "腾讯", "minimax", "快手", "生数科技", "小米",
    # 兼容旧英文/拼音名，避免历史数据误判为国外
    "deepseek", "alibaba cloud", "moonshot ai", "zhipu ai", "baidu",
    "bytedance", "tencent cloud", "kuaishou", "shengshu tech", "mimo",
    "tencent", "alibaba", "moonshot", "zhipu",
}


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
    official_url: str
    openness: str
    multimodal: str
    features: str
    cli_agent_support: str
    plugin_support: str
    web_app: str
    model_card: str
    release_notes: str
    license_terms: str
    subscription_price: str
    api_price: str
    discount: str
    source_status: str
    region: str
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
        html_text = raw.decode("utf-8", errors="replace")
        parser = TextExtractor()
        parser.feed(html_text)
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
        return "发现疑似优惠/免费额度： " + " / ".join(shorten(s, 120) for s in snippets)
    return "未发现明确优惠信息"


def infer_multimodal(config_value: str, text: str) -> str:
    if config_value:
        return config_value
    if find_keyword_snippets(text, MULTIMODAL_KEYWORDS, limit=1):
        return "是（页面检测到多模态描述，需复核）"
    return "未确认"


def infer_openness(config_value: str, text: str) -> str:
    if config_value:
        return config_value
    if find_keyword_snippets(text, OPEN_KEYWORDS, limit=1):
        return "可能开源/开放权重（需复核许可证）"
    return "未确认"


def shorten(value: str, width: int = 140) -> str:
    return textwrap.shorten(" ".join(value.split()), width=width, placeholder="...")


def html_escape(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#x27;")


def format_links_html(urls: Iterable[str], label: str = "链接") -> str:
    clean_urls = unique(urls)
    if not clean_urls:
        return "<span class='text-muted'>未配置</span>"
    return " ".join(f"<a href='{html_escape(url)}' target='_blank' class='btn-link'>{html_escape(label)}{i + 1}</a>" for i, url in enumerate(clean_urls))


def pick_note(model: dict[str, Any], provider: dict[str, Any], key: str, fallback: str = "未确认") -> str:
    return model.get(key) or provider.get(key) or fallback


def pick_web_app(model: dict[str, Any], provider: dict[str, Any]) -> str:
    return (
        model.get("web_app")
        or provider.get("web_app")
        or model.get("official_url")
        or provider.get("official_url")
        or "未配置"
    )


def collect_urls(provider: dict[str, Any], model: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for key in (
        "sources",
        "pricing_sources",
        "model_card_sources",
        "release_note_sources",
        "license_sources",
        "cli_agent_sources",
        "plugin_sources",
    ):
        urls.extend(provider.get(key, []))
        urls.extend(model.get(key, []))
    for key in ("official_url", "web_app", "weights_url"):
        for owner in (provider, model):
            value = owner.get(key)
            if value and value.startswith(("http://", "https://")):
                urls.append(value)
    return unique(urls)


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
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] discovery failed for {query!r}: {exc}")
    return unique(urls)[:max_results]


def build_rows(config: dict[str, Any], *, no_fetch: bool, discover: bool, max_discovered: int) -> list[ModelRow]:
    rows: list[ModelRow] = []
    for provider in config["providers"]:
        provider_name = provider["name"]
        region = "国内" if provider_name.lower() in DOMESTIC_PROVIDERS else "国外"
        for model in provider.get("models", []):
            model_name = model["name"]
            urls = collect_urls(provider, model)
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
                    official_url=pick_note(model, provider, "official_url", "未配置"),
                    openness=infer_openness(model.get("openness", ""), combined_text),
                    multimodal=infer_multimodal(model.get("multimodal", ""), combined_text),
                    features=features or "待补充",
                    cli_agent_support=pick_note(model, provider, "cli_agent_support"),
                    plugin_support=pick_note(model, provider, "plugin_support"),
                    web_app=pick_web_app(model, provider),
                    model_card=format_links_html(model.get("model_card_sources", provider.get("model_card_sources", [])), "Model Card"),
                    release_notes=format_links_html(
                        model.get("release_note_sources", provider.get("release_note_sources", [])),
                        "Release",
                    ),
                    license_terms=build_license_terms_html(provider, model),
                    subscription_price=subscription_price,
                    api_price=price_text,
                    discount=detect_discount(combined_text) if combined_text else model.get("discount_note", "未联网核验"),
                    source_status=source_status,
                    region=region,
                    sources=urls,
                )
            )
    return rows


def build_license_terms_html(provider: dict[str, Any], model: dict[str, Any]) -> str:
    parts = []
    license_note = pick_note(model, provider, "license_note", "")
    weights_url = pick_note(model, provider, "weights_url", "")
    commercial_use = pick_note(model, provider, "commercial_use_note", "")
    if license_note:
        parts.append(license_note)
    if weights_url:
        parts.append(f"<a href='{html_escape(weights_url)}' target='_blank' class='btn-link'>权重/仓库</a>")
    if commercial_use:
        parts.append(f"商用限制：{commercial_use}")
    return "<br>".join(parts) if parts else "未确认"


def summarize_fetches(fetches: list[FetchResult]) -> str:
    if not fetches:
        return "未配置来源"
    ok_count = sum(1 for item in fetches if item.ok)
    if ok_count == len(fetches):
        return f"已抓取 {ok_count}/{len(fetches)} 个来源"
    return f"已抓取 {ok_count}/{len(fetches)} (部分失败)"


def extract_rankings() -> dict[str, Any]:
    """Parse local HTML ranking lists and merge them dynamically."""
    dom_path = ROOT / "国产大模型能力全景排名.html"
    for_path = ROOT / "国外大模型能力全景排名.html"
    
    rankings = {
        "domestic": {"categories": {}, "companies": [], "details": []},
        "foreign": {"categories": {}, "companies": [], "details": []}
    }
    
    if dom_path.exists():
        dom_html = dom_path.read_text(encoding="utf-8")
        cats = re.findall(r'<article class="card category-card (coding|image|video|text)".*?>(.*?)</article>', dom_html, re.DOTALL)
        for cat, content in cats:
            items = re.findall(r'<div class="rank-item"><span class="rank[^"]*">(.*?)</span>\s*<div>\s*<div class="name">(.*?)</div>\s*<div class="desc">(.*?)</div>\s*</div>\s*(?:<span class="tag[^"]*">(.*?)</span>)?\s*</div>', content)
            rankings["domestic"]["categories"][cat] = [{"rank": r.strip(), "name": n.strip(), "desc": d.strip(), "tag": t.strip()} for r, n, d, t in items]
        
        comps = re.findall(r'<div class="company">\s*<h3>(.*?)</h3>\s*<div class="sub">(.*?)</div>\s*<div class="meter-row"><span>编程</span>.*?<b>(\d+)</b></div>\s*<div class="meter-row"><span>图片</span>.*?<b>(\d+)</b></div>\s*<div class="meter-row"><span>视频</span>.*?<b>(\d+)</b></div>\s*<div class="meter-row"><span>文本</span>.*?<b>(\d+)</b></div>\s*</div>', dom_html, re.DOTALL)
        rankings["domestic"]["companies"] = [{"name": c[0].strip(), "sub": c[1].strip(), "scores": {"coding": int(c[2]), "image": int(c[3]), "video": int(c[4]), "text": int(c[5])}} for c in comps]
        
        details = re.findall(r'<details(?: open)?>\s*<summary>(.*?)</summary>\s*<div class="inside">\s*(.*?)\s*</div>\s*</details>', dom_html, re.DOTALL)
        rankings["domestic"]["details"] = [{"title": t.strip(), "content": c.strip()} for t, c in details]

    if for_path.exists():
        for_html = for_path.read_text(encoding="utf-8")
        cats = re.findall(r'<article class="card category (coding|image|video|text)".*?>(.*?)</article>', for_html, re.DOTALL)
        for cat, content in cats:
            items = re.findall(r'<div class="item"><span class="rank[^"]*">(.*?)</span>\s*<div>\s*<div class="name">(.*?)</div>\s*<div class="desc">(.*?)</div>\s*</div>\s*(?:<span class="tag[^"]*">(.*?)</span>)?\s*</div>', content)
            rankings["foreign"]["categories"][cat] = [{"rank": r.strip(), "name": n.strip(), "desc": d.strip(), "tag": t.strip()} for r, n, d, t in items]
            
        comps = re.findall(r'<div class="company"><h3>(.*?)</h3>\s*<div class="sub">(.*?)</div>\s*<div class="mrow"><span>编程</span>.*?<b>(\d+)</b></div>\s*<div class="mrow"><span>图片</span>.*?<b>(\d+)</b></div>\s*<div class="mrow"><span>视频</span>.*?<b>(\d+)</b></div>\s*<div class="mrow"><span>文本</span>.*?<b>(\d+)</b></div></div>', for_html, re.DOTALL)
        rankings["foreign"]["companies"] = [{"name": c[0].strip(), "sub": c[1].strip(), "scores": {"coding": int(c[2]), "image": int(c[3]), "video": int(c[4]), "text": int(c[5])}} for c in comps]

        details = re.findall(r'<details(?: open)?>\s*<summary>(.*?)</summary>\s*<div class="inside">\s*(.*?)\s*</div>\s*</details>', for_html, re.DOTALL)
        rankings["foreign"]["details"] = [{"title": t.strip(), "content": c.strip()} for t, c in details]
        
    return rankings


def render_report(rows: list[ModelRow], config: dict[str, Any], rankings: dict[str, Any]) -> str:
    """Generate high-fidelity consolidated HTML dashboard."""
    generated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    # Pre-render category grids
    def render_cat_cards(region: str) -> str:
        reg_data = rankings.get(region, {})
        categories = reg_data.get("categories", {})
        html_out = ""
        cat_names = {"coding": "编程能力", "image": "图片生成", "video": "视频生成", "text": "文本整合与表达"}
        for cat_key, cat_name in cat_names.items():
            items = categories.get(cat_key, [])
            if not items:
                continue
            html_out += f"""
            <article class="card category-card {cat_key}">
                <div class="cardhead"><h3>{cat_name}</h3></div>
                <div class="cardbody"><div class="ranklist">
            """
            for item in items:
                r = item["rank"]
                c_rank_class = "r1" if r == "1" else "r2" if r == "2" else "r3" if r == "3" else ""
                html_out += f"""
                <div class="item">
                    <span class="rank {c_rank_class}">{html_escape(r)}</span>
                    <div>
                        <div class="name">{html_escape(item["name"])}</div>
                        <div class="desc">{html_escape(item["desc"])}</div>
                    </div>
                    {f'<span class="tag">{html_escape(item["tag"])}</span>' if item["tag"] else ""}
                </div>
                """
            html_out += "</div></div></article>"
        return html_out

    # Pre-render company score lists
    def render_companies(region: str) -> str:
        reg_data = rankings.get(region, {})
        comps = reg_data.get("companies", [])
        html_out = ""
        for comp in comps:
            scores = comp["scores"]
            html_out += f"""
            <div class="company-card">
                <h3>{html_escape(comp["name"])}</h3>
                <div class="company-sub">{html_escape(comp["sub"])}</div>
                <div class="mrow"><span>编程</span><div class="meter"><span style="width:{scores['coding']*10}%"></span></div><b>{scores['coding']}</b></div>
                <div class="mrow"><span>图片</span><div class="meter"><span style="width:{scores['image']*10}%"></span></div><b>{scores['image']}</b></div>
                <div class="mrow"><span>视频</span><div class="meter"><span style="width:{scores['video']*10}%"></span></div><b>{scores['video']}</b></div>
                <div class="mrow"><span>文本</span><div class="meter"><span style="width:{scores['text']*10}%"></span></div><b>{scores['text']}</b></div>
            </div>
            """
        return html_out

    # Pre-render decision guides
    def render_guides(region: str) -> str:
        reg_data = rankings.get(region, {})
        details = reg_data.get("details", [])
        html_out = ""
        for item in details:
            html_out += f"""
            <details>
                <summary>{html_escape(item["title"])}</summary>
                <div class="inside">{item["content"]}</div>
            </details>
            """
        return html_out

    # Compile table body
    table_rows_html = ""
    for row in rows:
        region_badge = f"<span class='badge-region {('domestic' if row.region == '国内' else 'foreign')}'>{row.region}</span>"
        table_rows_html += f"""
        <tr data-region="{row.region}">
            <td><strong>{html_escape(row.provider)}</strong></td>
            <td><strong>{html_escape(row.model)}</strong></td>
            <td>{region_badge}</td>
            <td><a href="{html_escape(row.official_url)}" target="_blank" class="btn-link">访问</a></td>
            <td>{html_escape(row.openness)}</td>
            <td>{html_escape(row.cli_agent_support)}</td>
            <td>{html_escape(row.plugin_support)}</td>
        </tr>
        """

    # Primary dashboard layout HTML template
    html_template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI 大模型能力与信息全景控制台</title>
  <style>
    :root {{
      --bg-primary: #080c14;
      --bg-secondary: #0e1320;
      --bg-tertiary: #1b2234;
      --accent: #2563eb;
      --accent-glow: rgba(37, 99, 235, 0.4);
      --text-primary: #f8fafc;
      --text-secondary: #94a3b8;
      --text-muted: #64748b;
      --border: rgba(255, 255, 255, 0.08);
      --border-active: rgba(37, 99, 235, 0.4);
      --card-bg: rgba(14, 19, 32, 0.7);
      --green: #10b981;
      --orange: #f59e0b;
      --red: #ef4444;
      --shadow: 0 16px 40px rgba(0, 0, 0, 0.35);
      --radius: 18px;
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: radial-gradient(circle at 10% 20%, #151d30 0%, #080c14 90%);
      color: var(--text-primary);
      line-height: 1.6;
    }}
    .hero {{
      padding: 60px 20px 40px;
      border-bottom: 1px solid var(--border);
      background: linear-gradient(180deg, rgba(14,19,32,0.8) 0%, rgba(8,12,20,0.9) 100%);
    }}
    .wrap {{ max-width: 1400px; margin: auto; }}
    .hero h1 {{ font-size: clamp(28px, 4vw, 46px); margin: 0 0 12px; letter-spacing: -1px; background: linear-gradient(90deg, #60a5fa, #34d399); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
    .hero p {{ margin: 0 0 24px; color: var(--text-secondary); font-size: 16px; max-width: 800px; }}
    .stats-row {{ display: flex; flex-wrap: wrap; gap: 20px; }}
    .stat-card {{
      background: var(--card-bg); border: 1px solid var(--border); border-radius: var(--radius);
      padding: 16px 24px; min-width: 180px; box-shadow: var(--shadow);
    }}
    .stat-card .label {{ color: var(--text-muted); font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; }}
    .stat-card .val {{ font-size: 28px; font-weight: 800; margin-top: 4px; color: #60a5fa; }}
    
    .nav-tabs {{
      position: sticky; top: 0; z-index: 100;
      background: rgba(8, 12, 20, 0.9); backdrop-filter: blur(16px);
      border-bottom: 1px solid var(--border);
    }}
    .nav-tabs-inner {{
      max-width: 1400px; margin: auto; padding: 12px 20px;
      display: flex; gap: 12px; overflow-x: auto;
    }}
    .tab-btn {{
      background: transparent; border: 1px solid transparent; color: var(--text-secondary);
      padding: 10px 20px; border-radius: 12px; font-size: 15px; font-weight: 600; cursor: pointer;
      transition: all 0.25s ease;
    }}
    .tab-btn:hover {{ color: var(--text-primary); background: rgba(255,255,255,0.05); }}
    .tab-btn.active {{
      color: var(--text-primary); background: var(--bg-tertiary);
      border-color: var(--border-active); box-shadow: 0 0 15px var(--accent-glow);
    }}
    
    .view-controls {{
      margin: 30px 0 20px; display: flex; flex-wrap: wrap; justify-content: space-between; gap: 16px; align-items: center;
    }}
    .region-tabs {{ display: flex; background: rgba(255,255,255,0.03); padding: 4px; border-radius: 12px; border: 1px solid var(--border); }}
    .region-btn {{
      background: transparent; border: none; color: var(--text-secondary); padding: 8px 20px; border-radius: 8px;
      font-size: 14px; font-weight: 700; cursor: pointer; transition: all 0.2s;
    }}
    .region-btn.active {{ background: var(--accent); color: #fff; box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3); }}
    
    .filter-group {{ display: flex; gap: 8px; overflow-x: auto; }}
    .filter-btn {{
      background: var(--bg-tertiary); border: 1px solid var(--border); color: var(--text-secondary);
      padding: 8px 16px; border-radius: 10px; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.2s;
    }}
    .filter-btn:hover, .filter-btn.active {{ color: var(--text-primary); border-color: var(--border-active); background: rgba(37,99,235,0.1); }}

    main {{ padding: 20px 20px 80px; }}
    .section-view {{ display: none; }}
    .section-view.active {{ display: block; }}
    
    .grid-ranks {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; margin-bottom: 40px; }}
    .card {{
      background: var(--card-bg); border: 1px solid var(--border); border-radius: var(--radius);
      box-shadow: var(--shadow); overflow: hidden; transition: all 0.3s;
    }}
    .card:hover {{ border-color: var(--border-active); transform: translateY(-3px); }}
    .cardhead {{ padding: 20px; border-bottom: 1px solid var(--border); background: rgba(255,255,255,0.01); }}
    .cardhead h3 {{ margin: 0; font-size: 18px; color: #60a5fa; }}
    .cardbody {{ padding: 20px; }}
    .ranklist {{ display: flex; flex-direction: column; gap: 12px; }}
    .item {{
      display: grid; grid-template-columns: 40px 1fr auto; gap: 12px; align-items: center;
      padding: 12px 14px; border: 1px solid var(--border); border-radius: 12px;
      background: rgba(255,255,255,0.02); transition: background 0.2s;
    }}
    .item:hover {{ background: rgba(255,255,255,0.04); }}
    .rank {{
      width: 30px; height: 30px; border-radius: 8px; display: grid; place-items: center;
      font-weight: 800; background: var(--bg-tertiary); color: var(--text-secondary);
    }}
    .rank.r1 {{ background: #fef08a; color: #854d0e; }}
    .rank.r2 {{ background: #e2e8f0; color: #334155; }}
    .rank.r3 {{ background: #ffedd5; color: #9a3412; }}
    .name {{ font-weight: 700; color: var(--text-primary); }}
    .desc {{ font-size: 12px; color: var(--text-secondary); margin-top: 2px; }}
    .tag {{
      font-size: 11px; padding: 4px 8px; border-radius: 99px;
      background: rgba(16, 185, 129, 0.15); color: var(--green); white-space: nowrap;
    }}
    .tag.none {{ background: rgba(239, 68, 68, 0.15); color: var(--red); }}
    .tag.mid {{ background: rgba(245, 158, 11, 0.15); color: var(--orange); }}

    .grid-companies {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 20px; margin-bottom: 40px; }}
    .company-card {{
      background: var(--card-bg); border: 1px solid var(--border); border-radius: var(--radius);
      padding: 20px; box-shadow: var(--shadow); transition: all 0.3s;
    }}
    .company-card:hover {{ border-color: var(--border-active); }}
    .company-card h3 {{ margin: 0 0 6px; font-size: 20px; color: var(--text-primary); }}
    .company-sub {{ font-size: 13px; color: var(--text-muted); min-height: 38px; margin-bottom: 12px; }}
    .mrow {{ display: grid; grid-template-columns: 50px 1fr 24px; gap: 8px; align-items: center; margin: 8px 0; font-size: 13px; }}
    .meter {{ height: 6px; background: rgba(255,255,255,0.05); border-radius: 99px; overflow: hidden; }}
    .meter span {{ display: block; height: 100%; background: linear-gradient(90deg, var(--accent), var(--green)); border-radius: 99px; }}
    .mrow b {{ text-align: right; color: var(--text-primary); }}

    details {{
      background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px;
      margin-bottom: 12px; box-shadow: var(--shadow); overflow: hidden;
    }}
    summary {{ cursor: pointer; padding: 16px 20px; font-weight: 700; color: var(--text-primary); outline: none; }}
    summary:hover {{ background: rgba(255,255,255,0.02); }}
    .inside {{ padding: 0 20px 20px; color: var(--text-secondary); border-top: 1px solid rgba(255,255,255,0.02); padding-top: 15px; }}

    .search-box {{
      position: relative; margin-bottom: 20px; display: flex; gap: 10px; max-width: 500px;
    }}
    .search-input {{
      flex: 1; padding: 12px 16px; border-radius: 12px; border: 1px solid var(--border);
      background: var(--bg-tertiary); color: var(--text-primary); font-size: 14px; transition: all 0.2s;
    }}
    .search-input:focus {{ outline: none; border-color: var(--accent); box-shadow: 0 0 10px var(--accent-glow); }}
    .results-count {{
      align-self: center; font-size: 13px; color: var(--text-muted);
    }}

    .table-container {{
      width: 100%; overflow-x: auto; background: var(--card-bg); border: 1px solid var(--border);
      border-radius: var(--radius); box-shadow: var(--shadow); margin-bottom: 30px;
    }}
    table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 13px; }}
    th, td {{ padding: 14px 16px; border-bottom: 1px solid var(--border); vertical-align: top; }}
    th {{ background: rgba(255,255,255,0.02); color: var(--text-secondary); font-weight: 600; text-transform: uppercase; font-size: 12px; letter-spacing: 0.5px; }}
    tr:hover td {{ background: rgba(255,255,255,0.01); }}
    tr:last-child td {{ border-bottom: none; }}
    .badge-region {{ padding: 4px 8px; border-radius: 6px; font-weight: 700; font-size: 11px; white-space: nowrap; }}
    .badge-region.domestic {{ background: rgba(59, 130, 246, 0.15); color: #60a5fa; }}
    .badge-region.foreign {{ background: rgba(139, 92, 246, 0.15); color: #a78bfa; }}
    .badge-status {{ color: var(--text-secondary); font-size: 12px; }}
    .price-highlight {{ font-weight: 600; color: #34d399; }}
    .btn-link {{ color: #60a5fa; text-decoration: none; font-weight: 600; transition: color 0.2s; }}
    .btn-link:hover {{ color: var(--text-primary); text-decoration: underline; }}
    
    .footer {{ text-align: center; color: var(--text-muted); font-size: 13px; margin-top: 60px; padding: 20px 0; border-top: 1px solid var(--border); }}
    .hidden {{ display: none !important; }}
    
    @media(max-width: 900px) {{
      .view-controls {{ flex-direction: column; align-items: stretch; }}
      .grid-ranks, .grid-companies {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>

  <header class="hero">
    <div class="wrap">
      <h1>AI 大模型能力与信息全景控制台</h1>
      <p>自动聚合官方数据源与实时搜寻结果，提供国内外主流 AI 大模型与厂商生态的多维度评测与实时信息数据库。</p>
      <div class="stats-row">
        <div class="stat-card">
          <div class="label">追踪模型总数</div>
          <div class="val">{len(rows)}</div>
        </div>
        <div class="stat-card">
          <div class="label">覆盖厂商总数</div>
          <div class="val">{len(config.get("providers", []))}</div>
        </div>
        <div class="stat-card">
          <div class="label">最后更新时间</div>
          <div class="val" style="font-size:16px; margin-top:14px; font-weight:600; color:#34d399;">{generated}</div>
        </div>
      </div>
    </div>
  </header>

  <nav class="nav-tabs">
    <div class="nav-tabs-inner">
      <button class="tab-btn active" onclick="switchTab('leaderboard')">📊 能力排行榜与生态</button>
      <button class="tab-btn" onclick="switchTab('database')">💾 模型详细信息数据库</button>
      <button class="tab-btn" onclick="switchTab('guide')">💡 场景化选型建议</button>
    </div>
  </nav>

  <main class="wrap">
    
    <!-- Tab 1: Leaderboards -->
    <div id="tab-leaderboard" class="section-view active">
      <div class="view-controls">
        <div class="region-tabs">
          <button class="region-btn active" onclick="switchRegion('domestic')">国内大模型</button>
          <button class="region-btn" onclick="switchRegion('foreign')">国外大模型</button>
        </div>
        <div class="filter-group">
          <button class="filter-btn active" onclick="filterRankCards('all', this)">全部榜单</button>
          <button class="filter-btn" onclick="filterRankCards('coding', this)">编程榜</button>
          <button class="filter-btn" onclick="filterRankCards('image', this)">图片榜</button>
          <button class="filter-btn" onclick="filterRankCards('video', this)">视频榜</button>
          <button class="filter-btn" onclick="filterRankCards('text', this)">文本表达榜</button>
        </div>
      </div>
      
      <!-- Domestic Leaderboard Container -->
      <div id="leaderboard-domestic" class="region-container">
        <h2>国内四大能力榜单</h2>
        <div class="grid-ranks">
          {render_cat_cards("domestic")}
        </div>
        <h2>国内公司大模型生态评分</h2>
        <div class="grid-companies">
          {render_companies("domestic")}
        </div>
      </div>

      <!-- Foreign Leaderboard Container -->
      <div id="leaderboard-foreign" class="region-container hidden">
        <h2>国外四大能力榜单</h2>
        <div class="grid-ranks">
          {render_cat_cards("foreign")}
        </div>
        <h2>国外公司大模型生态评分</h2>
        <div class="grid-companies">
          {render_companies("foreign")}
        </div>
      </div>
    </div>

    <!-- Tab 2: Database -->
    <div id="tab-database" class="section-view">
      <h2>所有模型详细追踪数据库</h2>
      <p style="color:var(--text-secondary); margin-bottom:20px;">包含官方地址、开源状态、API 价格、订阅价格、多模态支持等实时更新参数。</p>
      
      <div class="search-box">
        <input type="text" class="search-input" id="search-db" oninput="searchDatabase()" placeholder="输入厂商、模型名、价格、支持等关键词进行过滤...">
        <span class="results-count" id="results-lbl">共 {len(rows)} 个大模型信息</span>
      </div>

      <div class="table-container">
        <table id="db-table">
          <thead>
            <tr>
              <th>厂商</th>
              <th>模型系列</th>
              <th>区域</th>
              <th>官方链接</th>
              <th>开源状态</th>
              <th>CLI 支持</th>
              <th>插件工具支持</th>
            </tr>
          </thead>
          <tbody>
            {table_rows_html}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Tab 3: Decision Guide -->
    <div id="tab-guide" class="section-view">
      <div class="view-controls" style="margin-top: 10px;">
        <div class="region-tabs">
          <button class="region-btn active" id="guide-reg-dom" onclick="switchGuideRegion('domestic')">国内选型建议</button>
          <button class="region-btn" id="guide-reg-for" onclick="switchGuideRegion('foreign')">国外选型建议</button>
        </div>
      </div>
      
      <div id="guide-domestic" class="guide-container">
        <h2>国产大模型详细选型解读</h2>
        {render_guides("domestic")}
      </div>

      <div id="guide-foreign" class="guide-container hidden">
        <h2>国外大模型详细选型解读</h2>
        {render_guides("foreign")}
      </div>
    </div>

    <footer class="footer">
      AI 大模型全景控制台报告 · 适合大模型选型、价格比对和策划决策 · 更新数据保留完整来源链接以便人工校验
    </footer>
  </main>

  <script>
    // Tab switching logic
    function switchTab(tabId) {{
      document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
      document.querySelectorAll('.section-view').forEach(view => view.classList.remove('active'));
      
      const activeBtn = Array.from(document.querySelectorAll('.tab-btn')).find(btn => btn.getAttribute('onclick').includes(tabId));
      if (activeBtn) activeBtn.classList.add('active');
      document.getElementById('tab-' + tabId).classList.add('active');
    }}

    // Leaderboard region switching
    function switchRegion(regionId) {{
      document.querySelectorAll('#tab-leaderboard .region-btn').forEach(btn => btn.classList.remove('active'));
      const activeBtn = Array.from(document.querySelectorAll('#tab-leaderboard .region-btn')).find(btn => btn.getAttribute('onclick').includes(regionId));
      if (activeBtn) activeBtn.classList.add('active');
      
      if (regionId === 'domestic') {{
        document.getElementById('leaderboard-domestic').classList.remove('hidden');
        document.getElementById('leaderboard-foreign').classList.add('hidden');
      }} else {{
        document.getElementById('leaderboard-domestic').classList.add('hidden');
        document.getElementById('leaderboard-foreign').classList.remove('hidden');
      }}
    }}

    // Guide region switching
    function switchGuideRegion(regionId) {{
      document.querySelectorAll('#tab-guide .region-btn').forEach(btn => btn.classList.remove('active'));
      const activeBtn = Array.from(document.querySelectorAll('#tab-guide .region-btn')).find(btn => btn.getAttribute('onclick').includes(regionId));
      if (activeBtn) activeBtn.classList.add('active');

      if (regionId === 'domestic') {{
        document.getElementById('guide-domestic').classList.remove('hidden');
        document.getElementById('guide-foreign').classList.add('hidden');
      }} else {{
        document.getElementById('guide-domestic').classList.add('hidden');
        document.getElementById('guide-foreign').classList.remove('hidden');
      }}
    }}

    // Ranking category filter buttons
    function filterRankCards(cat, btn) {{
      const filterGroup = btn.parentElement;
      filterGroup.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const cards = document.querySelectorAll('.category-card');
      cards.forEach(card => {{
        if (cat === 'all') {{
          card.classList.remove('hidden');
        }} else {{
          card.classList.toggle('hidden', !card.classList.contains(cat));
        }}
      }});
    }}

    // Database search filter
    function searchDatabase() {{
      const query = document.getElementById('search-db').value.toLowerCase().strip();
      const rows = document.querySelectorAll('#db-table tbody tr');
      let matchedCount = 0;
      
      rows.forEach(row => {{
        const text = row.textContent.toLowerCase();
        if (text.includes(query)) {{
          row.classList.remove('hidden');
          matchedCount++;
        }} else {{
          row.classList.add('hidden');
        }}
      }});
      
      document.getElementById('results-lbl').textContent = '匹配到 ' + matchedCount + ' 个大模型信息';
    }}

    // JavaScript helper string trim
    String.prototype.strip = function() {{
      return this.replace(/^\\s+|\\s+$/g, '');
    }};
  </script>
</body>
</html>
"""
    return html_template


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an AI large-model tracing HTML report.")
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES, help="Path to model source JSON.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="HTML output path.")
    parser.add_argument("--no-fetch", action="store_true", help="Do not fetch web pages; generate from configured metadata only.")
    parser.add_argument("--discover", action="store_true", help="Use optional search APIs to discover extra URLs.")
    parser.add_argument("--max-discovered", type=int, default=3, help="Maximum discovered URLs per model/provider query.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_json(args.sources)
    rows = build_rows(config, no_fetch=args.no_fetch, discover=args.discover, max_discovered=args.max_discovered)
    rankings = extract_rankings()
    report = render_report(rows, config, rankings)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"Generated {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
