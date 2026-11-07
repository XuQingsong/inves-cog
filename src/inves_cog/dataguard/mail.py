"""Chinese data notices. Credentials stay in the server environment, never the outbox."""

import smtplib
import ssl
from email.message import EmailMessage
from hashlib import sha256

KINDS = {
    "complete": "完整",
    "not_due": "尚未到核查期限",
    "unknown": "核查未完成",
    "missing": "缺失",
    "partial": "不完整",
    "stale": "陈旧",
    "suspect": "数值可疑",
    "job_failed": "采集任务失败",
}
STATES = {
    "complete": "本轮完整",
    "not_due": "待发布后核查",
    "unknown": "需核查守护程序",
    "open": "待处理",
    "backfilling": "正在补数",
    "resolved": "已补齐",
    "unrecoverable": "补数未成功，需人工处理",
}


def compose(rows, *, daily=False, resources="资源状态尚未核实"):
    subject = f"数据{'日报' if daily else '提醒'}：{len(rows)} 项"
    lines = [subject]
    for r in rows:
        explanation = r["detail"].get("recovery_reason", "")
        lines.append(
            f"{r['dataset']} / {r['data_date']}：{KINDS.get(r['kind'], '待核实')}；"
            f"{STATES.get(r['status'], '待核实')}。影响：{r['detail'].get('impact', '相关数据展示')}。"
            f"系统已尝试补数 {r['attempts']} 次。" + (f"原因：{explanation}。" if explanation else "")
        )
    lines += [
        f"服务器资源：{resources}",
        "系统会复核补数结果。数值可疑不会自动改价；补数未成功时请核查来源与采集任务。",
        "只检测模式下不会自动补数。详情见网站“数据状态”。",
    ]
    return subject, "\n".join(lines)


class Mailer:
    def __init__(self, values, *, smtp=smtplib.SMTP, smtp_ssl=smtplib.SMTP_SSL):
        self.values, self.smtp, self.smtp_ssl = values, smtp, smtp_ssl

    @property
    def configured(self):
        return all(
            self.values.get("INVES_" + k)
            for k in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM", "ALERT_TO")
        )

    def send(self, event_key, subject, body):
        if not self.configured:
            return "邮件未配置"
        v = self.values
        message = EmailMessage()
        message["From"], message["To"], message["Subject"] = v["INVES_SMTP_FROM"], v["INVES_ALERT_TO"], subject
        message["Message-ID"] = f"<{sha256(event_key.encode()).hexdigest()}@inves-cog.alert>"
        message.set_content(body)
        # Do not log exceptions: SMTP providers can include login names or message content.
        try:
            port = int(v["INVES_SMTP_PORT"])
            implicit_tls = port in {465, 994}
            factory = self.smtp_ssl if implicit_tls else self.smtp
            options = {"context": ssl.create_default_context()} if implicit_tls else {}
            with factory(v["INVES_SMTP_HOST"], port, timeout=10, **options) as server:
                server.ehlo()
                if not implicit_tls:
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()
                server.login(v["INVES_SMTP_USER"], v["INVES_SMTP_PASSWORD"])
                if server.send_message(message):
                    return "邮件部分收件人发送失败，将重试"
            return "sent"
        except (OSError, ValueError, smtplib.SMTPException):
            return "邮件发送失败，将重试"
