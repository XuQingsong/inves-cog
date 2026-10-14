"""Handwritten recording checks for shared-call accounting."""
import hashlib
import json


def assert_usage_accounting(root, clock):
    from inves_cog.llm.client import Client, LLMUnavailable, canonical_payload
    from inves_cog.llm.transport import OpenAICompatibleTransport
    from inves_cog.ingest.http import Response

    payload = {'headline': 'Handwritten accounting fixture', 'body': 'Original fixture prose.'}
    digest = hashlib.sha256(canonical_payload(payload).encode()).hexdigest()
    folder = root / 'entity_tagging'; folder.mkdir(parents=True)
    path = folder / (digest + '.json')
    recording = {'task': 'entity_tagging', 'payload_sha256': digest, 'result': {'entities': []},
                 'usage': {'prompt_tokens': 11, 'completion_tokens': 3}}
    path.write_text(json.dumps(recording))
    rows = []
    client = Client(recordings=root, clock=clock, recorder=rows.append, monotonic=lambda: 0)
    with client.context(purpose='M1:layer1', info_ids=['news:fixture:1']):
        assert client.call('entity_tagging', payload) == {'entities': []}
    assert len(rows) == 1
    assert rows[0]['input_tokens'] == 11 and rows[0]['output_tokens'] == 3
    assert rows[0]['purpose'] == 'M1:layer1' and rows[0]['info_ids'] == ['news:fixture:1']
    assert rows[0]['created_at'] == clock.now_utc() and rows[0]['status'] == 'ok'
    assert rows[0]['model'] == 'deepseek-v4.1-flash'
    assert rows[0]['call_id'] and rows[0]['latency_ms'] >= 0
    recording.pop('usage'); path.write_text(json.dumps(recording))
    client.call('entity_tagging', payload)
    assert rows[-1]['input_tokens'] is None and rows[-1]['output_tokens'] is None
    assert rows[-1]['status'] == 'usage_missing'
    recording['error'] = 'handwritten timeout'; path.write_text(json.dumps(recording))
    try:client.call('entity_tagging', payload)
    except LLMUnavailable:pass
    else:raise AssertionError('recorded failure must be raised')
    assert rows[-1]['status'] == 'failed_usage_missing' and len(rows) == 3

    # The actual protocol response carries usage separately from the public
    # extraction dict; no extra metadata leaks into call(task,payload)->dict.
    config = {'LLM_STANDARD_API_KEY':'fixture-not-a-key',
              'LLM_STANDARD_BASE_URL':'https://example.invalid/v1',
              'LLM_STANDARD_API_STYLE':'openai-compatible'}
    def send(*args, **kwargs):
        return Response(200, {'choices':[{'message':{'content':'{"entities":[]}'}}],
                              'usage':{'prompt_tokens':7,'completion_tokens':2}})
    live_shape = Client(transport=OpenAICompatibleTransport(config, send=send),clock=clock,
                        recorder=rows.append,monotonic=lambda:0)
    assert live_shape.call('entity_tagging', payload) == {'entities':[]}
    assert rows[-1]['input_tokens'] == 7 and rows[-1]['output_tokens'] == 2
