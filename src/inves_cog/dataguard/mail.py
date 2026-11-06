"""Chinese data notices. Credentials stay in the server environment, never the outbox."""

import smtplib
import ssl
from email.message import EmailMessage
from hashlib import sha256

KINDS = {"missing": "缺失", "partial": "不完整", "stale": "陈旧", "suspect": "数值可疑", "job_failed": "采集任务失败"}
STATES = {"open": "待处理", "backfilling": "正在补数", "resolved": "已补齐", "unrecoverable": "补数未成功，需人工处理"}


def compose(rows, *, daily=False, resources="资源状态尚未核实"):
    subject = f"数据{'日报' if daily else '提醒'}：{len(rows)} 项"
    lines = [subject]
    for r in rows:
        lines.append(
            f"{r['dataset']} / {r['data_date']}：{KINDS.get(r['kind'], '待核实')}；"
            f"{STATES.get(r['status'], '待核实')}。影响：{r['detail'].get('impact', '相关数据展示')}。"
            f"系统已尝试补数 {r['attempts']} 次。"
        )
    lines += [
        f"服务器资源：{resources}",
        "系统会复核补数结果。数值可疑不会自动改价；补数未成功时请核查来源与采集任务。",
        "只检测模式下不会自动补数。详情见网站“数据状态”。",
    ]
    return subject, "\n".join(lines)


class Mailer:
    def __init__(self, values, *, smtp=smtplib.SMTP):
        self.values, self.smtp = values, smtp

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
            with self.smtp(v["INVES_SMTP_HOST"], int(v["INVES_SMTP_PORT"]), timeout=10) as server:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
                server.login(v["INVES_SMTP_USER"], v["INVES_SMTP_PASSWORD"])
                server.send_message(message)
            return "sent"
        except (OSError, ValueError, smtplib.SMTPException):
            return "邮件发送失败，将重试"
