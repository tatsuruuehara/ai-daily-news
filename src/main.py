import os
import json
import re
import time
import email.utils
import feedparser
import openai
import resend
from googlesearch import search as gsearch
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

CURATE_PROMPT = """あなたはAI/DX事業の経営者向けニュースキュレーターです。
読者は自らAI/DXコンサルティング事業を経営しており、クライアントへの提案ネタ・自社事業に活かせる具体的な情報を求めています。

## 読者が求める情報（優先度順）
1. **新モデル・新機能リリース** — Claude/GPT/Gemini等の具体的なアップデート内容。何ができるようになったか
2. **AIで成果を出した実例** — 売上向上・コスト削減・業務改善の具体的な数字付きケーススタディ
3. **AIエージェントの実践ノウハウ** — MCP, Claude Code, n8n, Dify等の具体的な使い方・構築Tips
4. **AI業界の競合・資金調達動向** — スタートアップの調達、M&A、プロダクトローンチ

## 絶対に含めないもの
- 3日以上前の古い記事（公開日が明らかに古いものは除外）
- 「AIが加速しています」「DXが重要です」のような抽象的な業界トレンド記事
- 初心者向け解説（「生成AIとは」「ChatGPTの使い方」系）
- 具体性のないポエム的な意見記事
- 古い情報の焼き直し

## 収集した記事
{articles}

## 出力ルール
- 必ず以下のJSON形式のみ出力（説明文不要）
- 海外記事のタイトル・要約は日本語に翻訳
- 各カテゴリ2-3件、合計5-10件に厳選
- 量より質。「経営者が明日使える情報か？」を基準に選定
- 各記事のURLは元記事のURLをそのまま使用すること（変更・省略しない）
- X（Twitter）の投稿は一次情報として非常に重要。特に以下は積極的に採用:
  - AIツールの具体的な使い方・Tips・ノウハウ投稿（Claude Code, MCP, Cursor等）
  - 実務でAIを活用した成果報告
  - 新機能の速報や第一報
  sourceには必ず「X (@ユーザー名)」の形式で投稿者を記載

```json
{{
  "highlight": {{
    "title": "今日最も重要なニュースの見出し",
    "summary": "2-3行で要約。経営者にとって何が重要かを明確に"
  }},
  "business": [
    {{"title": "記事タイトル（日本語）", "url": "元記事URL", "summary": "1-2行の日本語要約。具体的な数字や成果を含める", "source": "メディア名 or X(@ユーザー名)"}}
  ],
  "agent": [
    {{"title": "...", "url": "...", "summary": "...", "source": "..."}}
  ],
  "tech": [
    {{"title": "...", "url": "...", "summary": "...", "source": "..."}}
  ],
  "trend": "今日の動きから経営者が押さえるべきポイントを1-2行で。抽象論ではなく具体的なアクション示唆を含める"
}}
```

カテゴリ分類:
- business: 実例・ケーススタディ・資金調達・M&A（数字や具体的成果があるもの優先）
- agent: AIエージェント・MCP・自動化の実践Tips・新ツール（すぐ試せるもの優先）
- tech: 新モデル・新機能・API変更（「何ができるようになったか」が明確なもの優先）"""


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


def collect_rss() -> list[dict]:
    articles = []
    for source, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                published = entry.get("published", entry.get("updated", ""))
                if not is_recent(published):
                    continue
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


X_QUERIES = [
    # ニュース速報系
    "site:x.com Claude OR ChatGPT OR Gemini 新機能 OR release OR アップデート",
    "site:x.com AI スタートアップ OR 資金調達 OR 買収",
    # 実践ノウハウ・Tips系
    "site:x.com Claude Code 使い方 OR Tips OR ノウハウ OR 便利",
    "site:x.com MCP 設定 OR 構築 OR 連携 OR 活用",
    "site:x.com AI エージェント 作り方 OR 構築 OR 自動化 OR ワークフロー",
    "site:x.com 生成AI 業務効率化 OR 時短 OR 自動化 OR 活用事例",
    "site:x.com Cursor OR Cline OR Windsurf AI開発 OR コーディング",
    "site:x.com n8n OR Dify OR AI自動化 OR ノーコード",
]


def collect_x_posts() -> list[dict]:
    articles = []
    seen_urls = set()
    for query in X_QUERIES:
        try:
            results = gsearch(query, num_results=5, lang="ja", advanced=True)
            for r in results:
                url = r.url
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                articles.append({
                    "title": r.title or "",
                    "url": url,
                    "summary": r.description or "",
                    "source": "X (Twitter)",
                    "published": "",
                })
        except Exception as e:
            print(f"[WARN] X search failed for '{query}': {e}")
        time.sleep(2)
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
        "subject": f"AI Daily News - {date_str}",
        "html": html,
    })
    print(f"[OK] Email sent: {result}")


def main():
    from template import build_html

    now = datetime.now(JST)
    date_str = now.strftime("%Y/%m/%d")
    print(f"[INFO] AI Daily News - {date_str}")

    print("[1/4] Collecting RSS feeds...")
    articles = collect_rss()
    print(f"  -> {len(articles)} RSS articles")

    print("[2/4] Collecting X (Twitter) posts...")
    x_posts = collect_x_posts()
    print(f"  -> {len(x_posts)} X posts")
    articles.extend(x_posts)
    print(f"  -> {len(articles)} total articles collected")

    if not articles:
        print("[ERROR] No articles collected. Exiting.")
        return

    print("[3/4] Curating with GPT-4o...")
    data = curate(articles)
    total = len(data.get("business", [])) + len(data.get("agent", [])) + len(data.get("tech", []))
    print(f"  -> {total} articles selected")

    print("[4/4] Sending email...")
    html = build_html(data, date_str)
    send_email(html, date_str)

    print("[DONE]")


if __name__ == "__main__":
    main()
