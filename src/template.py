SOURCE_COLORS = {
    "AINOW": "#1a73e8",
    "ITmedia AI+": "#e64a19",
    "AIsmiley": "#ff6b35",
    "OpenAI Blog": "#10a37f",
    "Google AI Blog": "#4285f4",
    "TechCrunch AI": "#0a9e01",
    "MIT Technology Review": "#e5127d",
    "AWS AI Blog": "#ff9900",
    "BBC Technology": "#bb1919",
    "VentureBeat AI": "#2196F3",
}

DEFAULT_COLOR = "#667eea"


def build_html(by_source: dict, date_str: str) -> str:
    total = sum(len(items) for items in by_source.values())

    def article_card(item, accent):
        url = item.get("url", "#")
        image = item.get("image", "")
        img_html = ""
        if image:
            img_html = f"""
              <a href="{url}"><img src="{image}" alt="" width="100%" style="border-radius:8px;display:block;margin:0 0 12px 0;" /></a>"""
        return f"""
        <tr><td style="padding:0 0 12px 0;">
          <table width="100%" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
            <tr><td style="border-left:4px solid {accent};padding:16px 20px;">{img_html}
              <a href="{url}" style="color:#1a1a2e;font-size:15px;font-weight:700;text-decoration:none;line-height:1.4;">{item.get('title','')}</a>
              <p style="color:#555;font-size:13px;line-height:1.6;margin:8px 0 0 0;">{item.get('summary','')}</p>
              <p style="margin:10px 0 0 0;">
                <a href="{url}" style="color:{accent};font-size:12px;font-weight:600;text-decoration:none;">&#x2197; Read more</a>
              </p>
            </td></tr>
          </table>
        </td></tr>"""

    def source_section(source_name, items):
        accent = SOURCE_COLORS.get(source_name, DEFAULT_COLOR)
        cards = "".join(article_card(i, accent) for i in items)
        return f"""
        <tr><td style="padding:28px 0 12px 0;">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td style="background:{accent};width:4px;border-radius:2px;"></td>
              <td style="padding-left:12px;">
                <span style="font-size:18px;font-weight:800;color:#1a1a2e;">{source_name}</span>
                <span style="font-size:13px;color:#999;margin-left:8px;">{len(items)} articles</span>
              </td>
            </tr>
          </table>
        </td></tr>
        {cards}"""

    sections = "".join(source_section(s, items) for s, items in by_source.items())

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Hiragino Sans',sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f2f5;padding:24px 0;">
<tr><td align="center">
<table width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;">

  <tr><td style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);border-radius:16px 16px 0 0;padding:40px 32px;text-align:center;">
    <h1 style="color:#ffffff;font-size:28px;font-weight:800;margin:0 0 4px 0;letter-spacing:-0.5px;">AI Daily News</h1>
    <p style="color:rgba(255,255,255,0.85);font-size:14px;margin:0;">{date_str} &mdash; {total} articles</p>
  </td></tr>

  <tr><td style="background:#f7f8fa;padding:0 32px 32px 32px;border-radius:0 0 16px 16px;">
    <table width="100%" cellpadding="0" cellspacing="0">
      {sections}
    </table>
  </td></tr>

  <tr><td style="padding:24px 32px;text-align:center;">
    <p style="font-size:12px;color:#999;margin:0;">Powered by Claude API + Resend | AI Daily News</p>
  </td></tr>

</table>
</td></tr>
</table>
</body></html>"""
