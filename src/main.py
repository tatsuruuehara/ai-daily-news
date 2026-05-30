import os
import json
import re
import time
import email.utils
import urllib.request
import urllib.parse
import feedparser
import anthropic
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
    "note AI": "https://note.com/topic/ai/rss",
    "Zenn AI": "https://zenn.dev/topics/ai/feed",
    "はてブ AI": "https://b.hatena.ne.jp/search/tag?q=AI&mode=rss",
    "Publickey": "https://www.publickey1.jp/atom.xml",
    "kirekaku": "https://kirekaku.com/feed",
    "BUSINESS AI": "https://business-ai.jp/feed",
}

CURATE_PROMPT = """あなたはAI実践者向けの情報キュレーターです。
読者はAI/DXコンサルティング事業の経営者で、自ら手を動かしてAIツールを使い倒すタイプです。
「明日すぐ試せる具体的なノウハウ」を最も求めています。

## 読者が求める情報（優先度順）
1. **AIツールの実践ガイド・Tips** — Claude Code, MCP, n8n, Cursor, Dify等の具体的な使い方・構築手順・設定方法。ステップバイステップで再現できるもの最優先
2. **AI活用の構築事例** — 「こう作った」「こう自動化した」という実装寄りの事例。業務フロー自動化、X運用自動化、データ分析自動化など
3. **新モデル・新機能リリース** — Claude/GPT/Gemini等の具体的なアップデート。「何ができるようになったか」「どう使うか」が明確なもの
4. **AI業界の競合・資金調達動向** — スタートアップの調達、M&A、新プロダクト

## 読者が好む記事の具体例
- 「n8n完全攻略ロードマップ：登録からAIエージェント構築まで」のような包括的ガイド
- 「Claude Codeに/usageが追加。コスト管理が可能に」のような新機能の具体的活用法
- 「X運用をClaude Codeで完全自動化する手順」のようなステップバイステップ解説
- 「MCPサーバーを自作してプリンター連携した」のような個人の実装事例

## 絶対に含めないもの
- 「AIが加速しています」「DXが重要です」のような抽象的な業界トレンド記事
- 初心者向け解説（「生成AIとは」「ChatGPTの使い方入門」系）
- 具体性のないポエム的な意見記事・感想文
- 古い情報の焼き直し、3日以上前の記事
- 具体的な手順やコードがない「○○がすごい」だけの記事

## 収集した記事
{articles}

## 出力ルール
- 必ず以下のJSON形式のみ出力（説明文不要）
- 海外記事のタイトル・要約は日本語に翻訳
- 各カテゴリ2-3件、合計5-10件に厳選
- 量より質。「読んですぐ手を動かせるか？」を基準に選定
- 各記事のURLは元記事のURLをそのまま使用すること（変更・省略しない）
- noteやZennの実践記事は積極的に採用すること

```json
{{
  "highlight": {{
    "title": "今日最も実践的で価値のある記事の見出し",
    "summary": "2-3行で要約。何ができるようになるかを明確に"
  }},
  "howto": [
    {{"title": "記事タイトル（日本語）", "url": "元記事URL", "summary": "1-2行の要約。具体的な手順・ツール名を含める", "source": "メディア名"}}
  ],
  "agent": [
    {{"title": "...", "url": "...", "summary": "...", "source": "..."}}
  ],
  "tech": [
    {{"title": "...", "url": "...", "summary": "...", "source": "..."}}
  ],
  "trend": "今日の情報から実践者が押さえるべきポイントを1-2行で。「○○を試すべき」のような具体的アクション示唆"
}}
```

カテゴリ分類:
- howto: 実践ガイド・チュートリアル・構築事例・Tips（すぐ試せるもの最優先）
- agent: AIエージェント・MCP・自動化ワークフローの新ツール・新手法
- tech: 新モデル・新機能・API変更・資金調達（「何ができるようになったか」が明確なもの）"""


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
    '(Claude Code OR Claude OR Anthropic) -is:retweet lang:ja',
    '(ChatGPT OR Gemini OR OpenAI) -is:retweet lang:ja',
    '(AIエージェント OR MCP OR 生成AI) -is:retweet lang:ja',
    '(Cursor OR Cline OR n8n OR Dify) AI -is:retweet lang:ja',
    'AI (資金調達 OR スタートアップ OR 速報) -is:retweet lang:ja',
]

MIN_LIKES = 500


def _x_search(query: str, bearer_token: str) -> dict:
    params = urllib.parse.urlencode({
        "query": query,
        "max_results": 50,
        "sort_order": "relevancy",
        "tweet.fields": "created_at,author_id,text,public_metrics,entities",
        "expansions": "author_id",
        "user.fields": "username,name",
    })
    url = f"https://api.twitter.com/2/tweets/search/recent?{params}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {bearer_token}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  [WARN] X search failed: {e}")
        return {}


def collect_x_posts() -> list[dict]:
    bearer_token = os.environ.get("X_BEARER_TOKEN", "")
    if not bearer_token:
        print("  [WARN] X_BEARER_TOKEN not set, skipping")
        return []

    seen_ids = set()
    results = []

    for query in X_QUERIES:
        data = _x_search(query, bearer_token)
        tweets = data.get("data", [])
        users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}

        for tweet in tweets:
            tid = tweet["id"]
            if tid in seen_ids:
                continue
            seen_ids.add(tid)

            metrics = tweet.get("public_metrics", {})
            if metrics.get("like_count", 0) < MIN_LIKES:
                continue

            author = users.get(tweet.get("author_id"), {})
            username = author.get("username", "unknown")
            text = tweet.get("text", "")

            ext_urls = [u.get("expanded_url", "") for u in tweet.get("entities", {}).get("urls", []) if "x.com" not in u.get("expanded_url", "") and "twitter.com" not in u.get("expanded_url", "")]
            url = ext_urls[0] if ext_urls else f"https://x.com/{username}/status/{tid}"

            results.append({
                "title": text[:80].replace("\n", " "),
                "url": url,
                "summary": text[:400].replace("\n", " "),
                "source": f"X (@{username})",
                "published": tweet.get("created_at", ""),
            })

        time.sleep(1)

    results.sort(key=lambda a: a.get("published", ""), reverse=True)
    print(f"  -> {len(results)} X posts (from {len(seen_ids)} searched, likes>={MIN_LIKES})")
    return results[:20]


def curate(articles: list[dict]) -> dict:
    client = anthropic.Anthropic()
    articles_text = "\n\n".join(
        f"---\nTitle: {a['title']}\nSource: {a['source']}\nURL: {a['url']}\nPublished: {a['published']}\nSummary: {a['summary']}"
        for a in articles
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system="You are an AI news curator. Always respond with valid JSON only. No markdown fences, no explanation.",
        messages=[
            {"role": "user", "content": CURATE_PROMPT.format(articles=articles_text)},
        ],
    )

    text = response.content[0].text
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        return json.loads(json_match.group())
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

    print("[2/4] Collecting X posts...")
    x_posts = collect_x_posts()
    articles.extend(x_posts)
    print(f"  -> {len(articles)} total articles")

    if not articles:
        print("[ERROR] No articles collected. Exiting.")
        return

    print("[3/4] Curating with Claude...")
    data = curate(articles)
    total = len(data.get("howto", [])) + len(data.get("agent", [])) + len(data.get("tech", []))
    print(f"  -> {total} articles selected")

    print("[4/4] Sending email...")
    html = build_html(data, date_str)
    send_email(html, date_str)

    print("[DONE]")


if __name__ == "__main__":
    main()
