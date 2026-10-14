"""Append-only information identity, provenance and graceful recorded extraction."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import math
from html.parser import HTMLParser
from pathlib import Path
import re
import unicodedata
import yaml

KINDS = {'news', 'sec_8k', 'form4', 'app_rank', 'trend', 'site_change', 'macro', 'short_interest', 'options_stats'}
ROOT = Path(__file__).resolve().parents[3]


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
    def handle_data(self, data):
        self.parts.append(data)
    def handle_starttag(self, tag, attrs):
        if tag.lower() in {'p', 'div', 'br', 'li', 'tr'}:
            self.parts.append(' ')
    def handle_endtag(self, tag):
        if tag.lower() in {'p', 'div', 'li', 'tr'}:
            self.parts.append(' ')


def normalized_body(body):
    parser = TextParser()
    parser.feed(body)
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', ''.join(parser.parts))).strip()


def extraction_body(body):
    """Visible prose for model input; source_root normalization is unchanged."""
    visible=re.sub(r'<(script|style)\b[^>]*>.*?</\1\s*>','',body or '',flags=re.I|re.S)
    return normalized_body(visible)


def source_root(body, *, headline=None, provider=None, upstream_id=None):
    if provider and upstream_id is not None:
        return f'{provider}:{upstream_id}'
    if body is None:
        return None
    normalized=normalized_body(body)
    if not normalized:
        return None
    title = normalized_body(headline or '')
    identity = title + '\n' + normalized if len(normalized) < 300 and title else normalized
    return 'sha256:' + hashlib.sha256(identity.encode('utf-8')).hexdigest()


def source_level(source, *, path=None):
    mapping = yaml.safe_load(Path(path or ROOT / 'config/source_levels.yaml').read_text())['sources']
    return mapping.get(source, 4)


def make_item(kind, source, native_id, *, headline, body, clock, published_at=None,
              url=None, tickers=(), payload=None, upstream_provider=None, upstream_id=None):
    if kind not in KINDS or not source or native_id is None or not str(native_id) or not headline:
        raise ValueError('Invalid information identity or required headline')
    if published_at is not None:
        if published_at.tzinfo is None:
            raise ValueError('published_at must carry a timezone')
        published_at = published_at.astimezone(timezone.utc)
    return {'info_id': f'{kind}:{source}:{native_id}', 'kind': kind, 'published_at': published_at,
            'first_seen_at': clock.now_utc(), 'source': source, 'source_root': source_root(body, headline=headline, provider=upstream_provider, upstream_id=upstream_id),
            'source_level': source_level(source), 'headline': headline, 'body': body, 'summary': body[:500] if body is not None else None,
            'url': url, 'tickers': list(tickers), 'entities': [], 'embedding': None, 'extraction_status': 'pending',
            'flags': [] if published_at is not None else ['published_at_missing'], 'payload': payload or {},
            'is_guidance': None, 'guidance_direction': None, 'is_rating_change': None, 'extraction_source': {}}


class InfoStore:
    def __init__(self):
        self.items, self.versions = {}, []
        self.counts = {'collected': 0, 'inserted': 0, 'deduped': 0}

    def put(self, item):
        item = deepcopy(item)
        item['summary'] = item['body'][:500] if item['body'] is not None else item.get('summary')
        self.counts['collected'] += 1
        identity = item['info_id']
        if identity not in self.items:
            self.items[identity] = deepcopy(item)
            self.counts['inserted'] += 1
            return 'inserted'
        current = self.items[identity]
        if (current['headline'], current['body']) != (item['headline'], item['body']):
            self.versions.append({'info_id': identity, 'version_seen_at': item['first_seen_at'],
                                  'headline': item['headline'], 'body': item['body'],
                                  'raw': {'previous': deepcopy(current), 'incoming': deepcopy(item)}})
            immutable = {key: current[key] for key in ('published_at', 'first_seen_at', 'source_root')}
            current.update(deepcopy(item))
            current.update(immutable)
        self.counts['deduped'] += 1
        return 'deduped'

    def compact(self, as_of):
        for row in self.items.values():
            if as_of - row['first_seen_at'] > timedelta(days=90) and row['summary'] is not None:
                row['body'] = None


def record_extraction_error(result, task, exc):
    detail = {'type': type(exc).__name__, 'message': str(exc)}
    if exc.__cause__ is not None:
        detail['cause'] = {'type': type(exc.__cause__).__name__, 'message': str(exc.__cause__)}
    result.setdefault('extraction_source', {}).setdefault('errors', {})[task] = detail


def enrich(item, *, llm, embed, entities, clock):
    result = deepcopy(item)
    prose=extraction_body(item['body'])
    payload = {'headline': item['headline'], 'body': prose[:2000]}
    failed = False
    for entity in entities:
        haystack = (item['headline'] + ' ' + prose).casefold()
        terms = [entity['name'], *entity.get('aliases', [])]
        if set(entity.get('tickers', [])) & set(item['tickers']) or any(re.search(r'(?<!\w)' + re.escape(term.casefold()) + r'(?!\w)', haystack) for term in terms):
            result['entities'].append(entity['entity_id'])
    try:
        tags = llm.call('entity_tagging', payload)
        if not isinstance(tags.get('entities'), list) or not all(isinstance(e, str) for e in tags['entities']):
            raise ValueError('Invalid entity extraction shape')
        allowed = {e['entity_id'] for e in entities}
        result['entities'] = sorted(set(result['entities']) | {e for e in tags['entities'] if not allowed or e in allowed})
    except Exception as exc:
        record_extraction_error(result, 'entity_tagging', exc)
        failed = True
        result['flags'].append('entity_tagging_failed')
    if item['kind'] in {'news', 'sec_8k'}:
        try:
            fields = llm.call('info_fields_extraction', payload)
            for key in ('is_guidance', 'is_rating_change'):
                value = fields.get(key)
                if value is not None and not isinstance(value, bool):
                    raise ValueError('Invalid boolean extraction')
                result[key] = value
                if value is not None:
                    result['extraction_source'][key] = 'llm'
            direction = fields.get('guidance_direction')
            if direction is not None and direction not in {'up', 'down', 'maintain'}:
                raise ValueError('Invalid guidance direction')
            result['guidance_direction'] = direction
            if direction is not None:
                result['extraction_source']['guidance_direction'] = 'llm'
            if result['published_at'] is None and fields.get('published_at'):
                stamp = datetime.fromisoformat(fields['published_at'].replace('Z', '+00:00'))
                if stamp.tzinfo is None or stamp > clock.now_utc():
                    raise ValueError('Invalid extracted publication time')
                result['published_at'] = stamp.astimezone(timezone.utc)
                result['extraction_source']['published_at'] = 'llm'
                result['flags'].remove('published_at_missing')
                result['flags'].append('published_at_extracted')
        except Exception as exc:
            record_extraction_error(result, 'info_fields_extraction', exc)
            failed = True
            for key in ('is_guidance', 'guidance_direction', 'is_rating_change'):
                result[key] = None
                result['extraction_source'].pop(key, None)
    result['extraction_status'] = 'failed' if failed else 'ok'
    if embed is not None:
        try:
            vector = embed(item['headline'] + '\n' + prose[:2000], model='text-embedding-v3', dimensions=1024)
            if not isinstance(vector, list) or len(vector) != 1024 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in vector):
                raise ValueError('Invalid embedding dimension or value')
            result['embedding'] = vector
        except Exception as exc:
            record_extraction_error(result, 'embedding', exc)
            result['flags'].append('embedding_failed')
    else:
        result['flags'].append('embedding_failed')
    return result
