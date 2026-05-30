import os
import json
import re
import feedparser
import openai
import resend
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))

RSS_FEEDS = {
    "TechCrunch": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "The Verge": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "VentureBeat": "https://venturebeat.com/category/ai/feed/",
    "MIT Tech Review": "https://www.technologyreview.com/feed/",
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "ITmedia AI+": "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml",
    "AINOW": "https://ainow.ai/feed/",
}

CURATE_PROMPT = """あなたはAIニュースキュレーターです。以下のRSSフィードから収集した記事群から、AI関連で最も重要・興味深い記事を厳選してください。

## 収集した記事
{articles}

## 出力ルール
- 必ず以下のJSON形式のみ出力（説明文不要）
- 海外記事のタイトル・要約は日本語に翻訳
- 各カテゴリ2-3件、合計5-10件に厳選
- 量より質を重視

```json
{{
  "highlight": {{
    "title": "今日最も重要なニュースの見出し",
    "summary": "2-3行で要約。なぜ重要かも含める"
  }},
  "business": [
    {{"title": "記事タイトル（日本語）", "url": "元記事URL", "summary": "1-2行の日本語要約", "source": "メディア名"}}
  ],
  "agent": [
    {{"title": "...", "url": "...", "summary": "...", "source": "..."}}
  ],
  "tech": [
    {{"title": "...", "url": "...", "summary": "...", "source": "..."}}
  ],
  "trend": "今日のAI業界全体のトレンドを1-2行でコメント"
}}
```

カテゴリ分類:
- business: AI × ビジネス活用（導入事例、DX、業務効率化、資金調達、M&A）
- agent: AIエージェント・自動化（エージェント、MCP、ワークフロー自動化、ツール連携）
- tech: AI開発・技術動向（新モデル、API、論文、ベンチマーク、オープンソース）"""


def collect_rss() -> list[dict]:
    articles = []
    for source, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:8]:
                published = entry.get("published", entry.get("updated", ""))
                articles.append({
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "summary": re.sub(r"<[^>]+>", "", entry.get("summary", ""))[:400],
                    "source": source,
                    "published": published,
                })
        except Exception as e:
            print(f"[WARN] Failed to fetch {source}: {e}")
    return articles


def curate(articles: list[dict]) -> dict:
    client = openai.OpenAI()
    articles_text = "\n\n".join(
        f"---\nTitle: {a['title']}\nSource: {a['source']}\nURL: {a['url']}\nPublished: {a['published']}\nSummary: {a['summary']}"
        for a in articles
    )

    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You are an AI news curator. Always respond with valid JSON only."},
            {"role": "user", "content": CURATE_PROMPT.format(articles=articles_text)},
        ],
    )

    text = response.choices[0].message.content
    return json.loads(text)


def send_email(html: str, date_str: str):
    resend.api_key = os.environ["RESEND_API_KEY"]
    to_email = os.environ.get("TO_EMAIL", "tatsuru.uehara@gmail.com")

    result = resend.Emails.send({
        "from": "AI Daily News <onboarding@resend.dev>",
        "to": [to_email],
        "subject": f"\U0001f916 AI Daily News - {date_str}",
        "html": html,
    })
    print(f"[OK] Email sent: {result}")


def main():
    from template import build_html

    now = datetime.now(JST)
    date_str = now.strftime("%Y/%m/%d")
    print(f"[INFO] AI Daily News - {date_str}")

    print("[1/3] Collecting RSS feeds...")
    articles = collect_rss()
    print(f"  -> {len(articles)} articles collected")

    if not articles:
        print("[ERROR] No articles collected. Exiting.")
        return

    print("[2/3] Curating with GPT-4o...")
    data = curate(articles)
    total = len(data.get("business", [])) + len(data.get("agent", [])) + len(data.get("tech", []))
    print(f"  -> {total} articles selected")

    print("[3/3] Sending email...")
    html = build_html(data, date_str)
    send_email(html, date_str)

    print("[DONE]")


if __name__ == "__main__":
    main()
