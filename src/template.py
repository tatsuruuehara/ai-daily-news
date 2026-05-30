def build_html(data: dict, date_str: str) -> str:
    highlight = data.get("highlight", {})
    business = data.get("business", [])
    agent = data.get("agent", [])
    tech = data.get("tech", [])
    trend = data.get("trend", "")

    def article_card(item, accent):
        url = item.get('url', '#')
        source = item.get('source', '')
        source_icon = "&#x1D54F;" if "X" in source or "Twitter" in source else "&#x1F4F0;"
        return f"""
        <tr><td style="padding:0 0 16px 0;">
          <table width="100%" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
            <tr><td style="border-left:4px solid {accent};padding:20px 24px;">
              <a href="{url}" style="color:#1a1a2e;font-size:16px;font-weight:700;text-decoration:none;line-height:1.4;">{item.get('title','')}</a>
              <p style="color:#555;font-size:14px;line-height:1.6;margin:8px 0 0 0;">{item.get('summary','')}</p>
              <p style="margin:12px 0 0 0;">
                <span style="color:#aaa;font-size:12px;">{source_icon} {source}</span>
                <a href="{url}" style="color:{accent};font-size:12px;font-weight:600;text-decoration:none;margin-left:12px;">&#x2197; Read more</a>
              </p>
            </td></tr>
          </table>
        </td></tr>"""

    def section(title, emoji, items, accent):
        if not items:
            return ""
        cards = "".join(article_card(i, accent) for i in items)
        return f"""
        <tr><td style="padding:32px 0 12px 0;">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td style="background:{accent};width:4px;border-radius:2px;"></td>
              <td style="padding-left:12px;">
                <span style="font-size:20px;font-weight:800;color:#1a1a2e;">{emoji} {title}</span>
              </td>
            </tr>
          </table>
        </td></tr>
        {cards}"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Hiragino Sans',sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f2f5;padding:24px 0;">
<tr><td align="center">
<table width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;">

  <!-- HEADER -->
  <tr><td style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);border-radius:16px 16px 0 0;padding:40px 32px;text-align:center;">
    <h1 style="color:#ffffff;font-size:28px;font-weight:800;margin:0 0 4px 0;letter-spacing:-0.5px;">AI Daily News</h1>
    <p style="color:rgba(255,255,255,0.85);font-size:14px;margin:0;">{date_str}</p>
  </td></tr>

  <!-- BODY -->
  <tr><td style="background:#f7f8fa;padding:0 32px 32px 32px;border-radius:0 0 16px 16px;">

    <!-- HIGHLIGHT -->
    <tr><td style="padding:24px 32px 0 32px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background:linear-gradient(135deg,#fff7e6 0%,#fff1d4 100%);border-radius:12px;border:1px solid #ffd88a;">
        <tr><td style="padding:24px;">
          <p style="font-size:12px;font-weight:700;color:#c47d00;text-transform:uppercase;letter-spacing:1px;margin:0 0 8px 0;">&#x26A1; TODAY'S HIGHLIGHT</p>
          <p style="font-size:18px;font-weight:700;color:#1a1a2e;margin:0 0 8px 0;line-height:1.4;">{highlight.get('title','')}</p>
          <p style="font-size:14px;color:#555;line-height:1.7;margin:0;">{highlight.get('summary','')}</p>
        </td></tr>
      </table>
    </td></tr>

    <!-- SECTIONS -->
    <tr><td style="padding:0 32px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        {section("AI x Business", "&#x1F3E2;", business, "#4CAF50")}
        {section("AI Agent / Automation", "&#x1F916;", agent, "#2196F3")}
        {section("Tech & Research", "&#x2699;&#xFE0F;", tech, "#9C27B0")}
      </table>
    </td></tr>

    <!-- TREND -->
    <tr><td style="padding:16px 32px 32px 32px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background:linear-gradient(135deg,#e8f5e9 0%,#e3f2fd 100%);border-radius:12px;">
        <tr><td style="padding:20px 24px;">
          <p style="font-size:12px;font-weight:700;color:#2e7d32;text-transform:uppercase;letter-spacing:1px;margin:0 0 8px 0;">&#x1F4C8; TREND INSIGHT</p>
          <p style="font-size:14px;color:#333;line-height:1.7;margin:0;">{trend}</p>
        </td></tr>
      </table>
    </td></tr>

  </td></tr>

  <!-- FOOTER -->
  <tr><td style="padding:24px 32px;text-align:center;">
    <p style="font-size:12px;color:#999;margin:0;">Powered by Claude API + Resend | AI Daily News by tatsuruuehara</p>
  </td></tr>

</table>
</td></tr>
</table>
</body></html>"""
