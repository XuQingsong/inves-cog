"""Clock-injected job accounting and source health shared with M2."""
from datetime import timedelta
import time

from inves_cog.ingest.http import SourceError


class HealthBook:
    def __init__(self, *, clock, rows=None, persist=None):
        self.clock, self.rows, self.persist = clock, rows or {}, persist

    def record(self, source, *, success, count=0, latency=None, note=None,
               configured=True, confirmed_unavailable=False, degraded=False):
        now = self.clock.now_utc()
        old = self.rows.get(source, {})
        failures = 0 if success else old.get('consecutive_failures', 0) + 1
        last_success = now if success else old.get('last_success_at')
        if not configured or confirmed_unavailable:
            status = '未接通'
        elif success:
            status = 'degraded' if degraded else 'ok'
        elif failures >= 2 and last_success is not None and now - last_success > timedelta(hours=24):
            status = 'unavailable'
        elif degraded or failures >= 2:
            status = 'degraded'
        else:
            status = old.get('status', 'ok')
        row = {'source': source, 'last_success_at': last_success, 'last_attempt_at': now, 'status': status,
               'latency_sec': latency, 'items_last_run': count, 'note': note, 'consecutive_failures': failures}
        self.rows[source] = row
        if self.persist:
            self.persist(row)
        return row


class JobRunner:
    def __init__(self, *, clock, health, persist, params_version='p-2026.10',
                 monotonic=time.monotonic, timeout_seconds=1800):
        self.clock, self.health, self.persist = clock, health, persist
        self.params_version, self.monotonic, self.timeout_seconds = params_version, monotonic, timeout_seconds

    def run(self, task_name, source, operation, *, trade_date=None, configured=True):
        started, timer = self.clock.now_utc(), self.monotonic()
        row = {'task_name': task_name, 'trade_date': trade_date or self.clock.today_trade_date(),
               'started_at': started, 'ended_at': None, 'status': 'failed', 'processed_count': 0,
               'error_summary': None, 'params_version': self.params_version}
        try:
            if not configured:
                raise SourceError('Required source configuration absent', confirmed_unavailable=True)
            from inves_cog.ingest.deadline import budget
            with budget(self.timeout_seconds, self.monotonic):
                result = operation()
            duration = self.monotonic() - timer
            count = result.get('processed_count', 0)
            if duration > self.timeout_seconds:
                error=SourceError('Task exceeded its 30-minute budget')
                error.processed_count=count
                raise error
            degraded = result.get('status') == 'degraded'
            row.update(status='degraded' if degraded else 'ok', processed_count=count)
            self.health.record(source, success=True, count=count, latency=duration,
                               note=result.get('note'), degraded=degraded)
            return result
        except Exception as exc:
            row['processed_count'] = getattr(exc, 'processed_count', 0)
            row['error_summary'] = f'{type(exc).__name__}: {exc}'
            self.health.record(source, success=False, count=row['processed_count'],
                               latency=self.monotonic() - timer, note=row['error_summary'], configured=configured,
                               confirmed_unavailable=getattr(exc, 'confirmed_unavailable', False))
            return {'status': 'failed', 'processed_count': row['processed_count'], 'error': row['error_summary']}
        finally:
            row['ended_at'] = self.clock.now_utc()
            self.persist(row)
