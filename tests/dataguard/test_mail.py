from datetime import datetime, timezone
import pytest
from inves_cog.dataguard.mail import Mailer, compose

pytestmark = pytest.mark.phase1_blocking
NOW = datetime(2026, 11, 7, tzinfo=timezone.utc)


def test_unconfigured_does_not_connect_or_expose_credentials():
    mailer = Mailer({}, smtp=lambda *a, **k: pytest.fail('unconfigured SMTP attempted'))
    assert mailer.send('gap:1', 'subject', 'body') == '邮件未配置'


def test_merge_gap_impact_and_resolution_are_chinese_and_escape_no_secrets():
    subject, body = compose([{'dataset':'波动率', 'data_date':'2026-11-05', 'kind':'stale',
                             'status':'open', 'detail':{'impact':'晴雨表恐慌情绪可能被低估'}, 'attempts':0},
                            {'dataset':'期权成交', 'data_date':'2026-11-05', 'kind':'missing',
                             'status':'resolved', 'detail':{'impact':'资金判断'}, 'attempts':1}])
    assert '波动率' in body and '期权成交' in body and '已补齐' in body
    assert '晴雨表' in body and '2026-11-05' in body
    assert '2' in subject


def test_starttls_then_login_and_stable_message_identifier():
    trace = []
    class SMTP:
        def __init__(self, host, port, timeout): trace.append(('connect',host,port))
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def ehlo(self): trace.append('ehlo')
        def starttls(self, **kw): trace.append('tls')
        def login(self, user, password): trace.append('login')
        def send_message(self, message): trace.append(message)
    values = dict(INVES_SMTP_HOST='smtp.gmail.com', INVES_SMTP_PORT='587', INVES_SMTP_USER='test@example.test',
                  INVES_SMTP_PASSWORD='fixture-only', INVES_SMTP_FROM='test@example.test',
                  INVES_ALERT_TO='recipient@example.test')
    m = Mailer(values, smtp=SMTP)
    assert m.send('same-event', '数据提醒', '缺失') == 'sent'
    first = trace[-1]['Message-ID']
    assert m.send('same-event', '数据提醒', '缺失') == 'sent'
    assert trace[-1]['Message-ID'] == first
    assert trace.index('tls') < trace.index('login')
