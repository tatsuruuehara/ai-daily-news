import os
import json
import re
import email.utils
import urllib.request
from pathlib import Path
import feedparser
from google import genai
import resend
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
HISTORY_PATH = Path(__file__).resolve().parent.parent / "data" / "history.json"
MAX_HISTORY = 30

RSS_FEEDS = {
    "AINOW": "https://ainow.ai/feed",
    "ITmedia AI+": "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml",
    "AIsmiley": "https://aismiley.co.jp/ai_news/feed/",
    "OpenAI Blog": "https://openai.com/blog/rss.xml",
    "Google AI Blog": "https://blog.google/technology/ai/rss/",
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "MIT Technology Review": "https://www.technologyreview.com/feed/",
    "AWS AI Blog": "https://aws.amazon.com/blogs/machine-learning/feed/",
    "BBC Technology": "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "VentureBeat AI": "https://venturebeat.com/category/ai/feed",
}

MAX_AGE_DAYS = 3


def is_recent(published_str: str) -> bool:
    if not published_str:
        return True
    try:
        parsed = email.utils.parsedate_tz(published_str)
        if parsed:
            ts = email.utils.mktime_tz(parsed)
            pub_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            return (datetime.now(timezone.utc) - pub_dt).days <= MAX_AGE_DAYS
    except Exception:
        pass
    return True


def fetch_og_image(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="ignore")[:15000]
        m = re.search(r'property="og:image"[^>]+content="([^"]+)"', html)
        if not m:
            m = re.search(r'content="([^"]+)"[^>]+property="og:image"', html)
        return m.group(1) if m else ""
    except Exception:
        return ""


def get_image_from_entry(entry) -> str:
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        return entry.media_thumbnail[0].get("url", "")
    if hasattr(entry, "media_content") and entry.media_content:
        for mc in entry.media_content:
            if mc.get("medium") == "image" or mc.get("type", "").startswith("image"):
                return mc.get("url", "")
    if hasattr(entry, "enclosures") and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get("type", "").startswith("image"):
                return enc.get("href", enc.get("url", ""))
    return ""


def collect_rss() -> list[dict]:
    articles = []
    for source, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                published = entry.get("published", entry.get("updated", ""))
                if not is_recent(published):
                    continue
                image = get_image_from_entry(entry)
                articles.append({
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "summary": re.sub(r"<[^>]+>", "", entry.get("summary", ""))[:400],
                    "source": source,
                    "published": published,
                    "image": image,
                })
        except Exception as e:
            print(f"[WARN] Failed to fetch {source}: {e}")

    print("  Fetching article images...")
    for a in articles:
        if not a["image"]:
            a["image"] = fetch_og_image(a["url"])

    return articles


def load_history() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    try:
        return json.loads(HISTORY_PATH.read_text())
    except Exception:
        return []


def save_history(history: list[dict]):
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history[-MAX_HISTORY:], ensure_ascii=False, indent=2))


def get_click_feedback() -> list[dict]:
    resend.api_key = os.environ.get("RESEND_API_KEY", "")
    if not resend.api_key:
        return []

    history = load_history()
    clicked = []

    for record in history:
        email_id = record.get("email_id")
        if not email_id or record.get("clicks_checked"):
            continue

        try:
            email_data = resend.Emails.get(email_id)
            clicks = email_data.get("clicks", [])
            for click in clicks:
                click_url = click.get("url", "") if isinstance(click, dict) else str(click)
                for article in record.get("articles", []):
                    if article.get("url") == click_url:
                        clicked.append({
                            "title": article["title"],
                            "source": article["source"],
                        })
            record["clicks_checked"] = True
        except Exception as e:
            print(f"[WARN] Failed to get clicks for {email_id}: {e}")

    save_history(history)
    return clicked


def build_preference_context(clicked: list[dict]) -> str:
    if not clicked:
        return ""

    titles = "\n".join(f"- {c['title']}（{c['source']}）" for c in clicked[-20:])
    return f"""

## 過去にクリックされた記事（読者が実際に興味を持った記事）
{titles}

上記の傾向を考慮して、似たテーマ・トピックの記事を優先的に選んでください。"""


CURATE_SYSTEM_BASE = """\
あなたはAIニュースキュレーターです。以下の記事一覧から、重要度と読者の興味に基づいて上位15件を厳選してください。

## 読者の興味
- AIエージェント・自動化（MCP、Claude Code、n8n、ワークフロー自動化）
- AI開発・技術動向（新モデルリリース、API、フレームワーク）
- AI × ビジネス活用（業務効率化、DX、導入事例）
- 実践的なハウツー・Tips

## 選定基準
- 新規性が高い（新リリース、新機能、ブレイクスルー）
- 実用性が高い（すぐ試せる、業務に活かせる）
- 業界インパクトが大きい

## 出力形式
JSON配列のみ出力。各要素:
{"index": N, "title": "日本語タイトル", "summary": "日本語で1-2行の要約"}

英語記事は日本語に翻訳、日本語記事はそのまま出力。indexは入力の番号に対応。"""


def curate_and_translate(articles: list[dict], clicked: list[dict]) -> list[dict]:
    system_prompt = CURATE_SYSTEM_BASE + build_preference_context(clicked)

    text_block = "\n---\n".join(
        f"[{i}] [{a['source']}] {a['title']}\n{a['summary'][:200]}"
        for i, a in enumerate(articles)
    )

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=text_block,
        config=genai.types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=16384,
            thinking_config=genai.types.ThinkingConfig(thinking_budget=0),
        ),
    )

    try:
        text = response.text
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        json_match = re.search(r'\[.*\]', text, re.DOTALL)
        selected = json.loads(json_match.group()) if json_match else json.loads(text)

        result = []
        for t in selected[:15]:
            idx = t.get("index", -1)
            if 0 <= idx < len(articles):
                article = articles[idx].copy()
                article["title"] = t.get("title", article["title"])
                article["summary"] = t.get("summary", article["summary"])
                result.append(article)
        return result
    except Exception as e:
        print(f"[WARN] Curation failed, returning all articles: {e}")
        return articles


def send_email(html: str, date_str: str) -> str:
    resend.api_key = os.environ["RESEND_API_KEY"]
    to_email = os.environ.get("TO_EMAIL", "tatsuru.uehara@gmail.com")

    result = resend.Emails.send({
        "from": "AI Daily News <onboarding@resend.dev>",
        "to": [to_email],
        "subject": f"AI Daily News - {date_str}",
        "html": html,
    })
    email_id = result.get("id", "") if isinstance(result, dict) else ""
    print(f"[OK] Email sent: {result}")
    return email_id


def main():
    from template import build_html

    now = datetime.now(JST)
    date_str = now.strftime("%Y/%m/%d")
    print(f"[INFO] AI Daily News - {date_str}")

    print("[1/4] Loading click history...")
    clicked = get_click_feedback()
    print(f"  -> {len(clicked)} clicked articles found")

    print("[2/4] Collecting RSS feeds...")
    articles = collect_rss()
    print(f"  -> {len(articles)} articles collected")

    if not articles:
        print("[ERROR] No articles collected. Exiting.")
        return

    print("[3/4] Curating top 15 + translating...")
    articles = curate_and_translate(articles, clicked)
    print(f"  -> {len(articles)} articles selected")

    print("[4/4] Sending email...")
    by_source = {}
    for a in articles:
        by_source.setdefault(a["source"], []).append(a)

    html = build_html(by_source, date_str)
    email_id = send_email(html, date_str)

    history = load_history()
    history.append({
        "date": date_str,
        "email_id": email_id,
        "articles": [{"title": a["title"], "url": a["url"], "source": a["source"]} for a in articles],
    })
    save_history(history)

    print("[DONE]")


if __name__ == "__main__":
    main()
