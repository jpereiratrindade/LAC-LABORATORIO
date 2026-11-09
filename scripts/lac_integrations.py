#!/usr/bin/env python3
"""Optional local adapters. Python standard library only; never writes LAC events."""
import argparse
import base64
from datetime import datetime, timedelta, timezone
import http.client
import ipaddress
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit

MAX_BYTES = 1024 * 1024


def now():
    return datetime.now(timezone.utc).isoformat()


def local_endpoint(value, allow_lan=False):
    url = urlsplit(value)
    host = url.hostname
    if allow_lan and host not in ('127.0.0.1', 'localhost'):
        address = ipaddress.IPv4Address(host)
        if not address.is_private or address.is_unspecified or address.is_multicast or address.is_link_local:
            raise ValueError('Only explicit private LAN IPv4 addresses are allowed')
    if (url.scheme != 'http' or not host or (not allow_lan and host not in ('127.0.0.1', 'localhost'))
            or url.username or url.password or url.path not in ('', '/')
            or url.query or url.fragment):
        raise ValueError('Use http://127.0.0.1:PORT, without credentials or paths')
    port = url.port or 80
    if not 1024 <= port <= 65535:
        raise ValueError('Port must be 1024-65535')
    return '127.0.0.1' if host == 'localhost' else host, port


def get_json(endpoint, path):
    host, port = local_endpoint(endpoint)
    conn = http.client.HTTPConnection(host, port, timeout=2)
    try:
        conn.request('GET', path)
        res = conn.getresponse()
        raw = res.read(MAX_BYTES + 1)
        if res.status != 200 or len(raw) > MAX_BYTES:
            raise ValueError('Local API failed or response exceeds 1 MiB')
        return json.loads(raw)
    finally:
        conn.close()


class Adapters:
    def __init__(self, path):
        self.path = Path(path)
        self.config = {'recoll': {'enabled': False, 'config_dir': '', 'roots': ''},
                       'activitywatch': {'enabled': False, 'url': 'http://127.0.0.1:5600', 'buckets': ''}}
        if self.path.exists():
            saved = json.loads(self.path.read_text())
            for name in self.config:
                self.config[name].update(saved.get(name, {}))

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix='.lac-integrations-', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(self.config, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def configure(self, args):
        name = args.get('integration')
        if name not in self.config:
            raise ValueError('Unknown integration')
        if args.get('enabled') not in ('true', 'false'):
            raise ValueError('enabled must be true or false')
        conf = self.config[name]
        conf['enabled'] = args['enabled'] == 'true'
        if name == 'recoll':
            for key in ('config_dir', 'roots'):
                if key in args:
                    conf[key] = args[key]
            if conf['enabled']:
                folder = Path(conf['config_dir'])
                if not folder.is_absolute() or not (folder / 'recoll.conf').is_file():
                    raise ValueError('An explicit Recoll directory containing recoll.conf is required')
                roots = conf['roots'].splitlines()
                if not roots or any(not Path(p).is_absolute() or not Path(p).is_dir() for p in roots):
                    raise ValueError('Specify authorized absolute directories, one per line')
        else:
            for key in ('url', 'buckets'):
                if key in args:
                    conf[key] = args[key]
            local_endpoint(conf['url'])
        self.save()
        return {'ok': True, 'integration': name, 'enabled': conf['enabled']}

    def status(self):
        result = {}
        for name, conf in self.config.items():
            item = dict(conf)
            item['state'] = 'disabled'
            if name == 'recoll':
                item['installed'] = bool(shutil.which('recollq') or shutil.which('recoll'))
                if conf['enabled']:
                    item['state'] = 'configured' if item['installed'] else 'missing'
            elif conf['enabled']:
                try:
                    buckets = get_json(conf['url'], '/api/0/buckets/')
                    if not isinstance(buckets, dict):
                        raise ValueError('Invalid buckets response')
                    # Metadata only. No titles or activity events are requested here.
                    item['available_buckets'] = [{'id': k, 'type': v.get('type', '')}
                                                 for k, v in list(buckets.items())[:100]]
                    item['state'] = 'reachable'
                except (OSError, ValueError, http.client.HTTPException):
                    item['state'] = 'unavailable'
            result[name] = item
        return result

    def search(self, args):
        conf = self.config['recoll']
        if not conf['enabled']:
            raise ValueError('Recoll integration is disabled')
        query = args.get('q', '').strip()
        if not query or len(query) > 1000:
            raise ValueError('Query must contain 1-1000 characters')
        limit = max(1, min(50, int(args.get('limit', 20))))
        executable = shutil.which('recollq')
        command = [executable] if executable else [shutil.which('recoll') or 'recoll', '-t']
        fields = ['url', 'title', 'mimetype', 'mtime', 'abstract']
        command += ['-c', conf['config_dir'], '-n', str(limit), '-F', ' '.join(fields), '--', query]
        # Temporary regular files bound memory use even if the executable is noisy.
        with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
            subprocess.run(command, stdout=output, stderr=errors, timeout=5, check=True)
            output.seek(0)
            raw = output.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError('Recoll response exceeds 1 MiB')
        roots = [Path(p).resolve() for p in conf['roots'].splitlines() if p]
        results = []
        for line in raw.decode('utf-8').splitlines():
            # -F encodes field values in base64. Empty fields retain their separators.
            cells = line.strip('\r').split(' ')
            if len(cells) != len(fields):
                continue  # Ignore Recoll's query and count headings.
            try:
                item = dict(zip(fields, [base64.b64decode(c, validate=True).decode('utf-8') for c in cells]))
            except (ValueError, UnicodeError):
                continue
            url = urlsplit(item['url'])
            if url.scheme != 'file' or url.netloc not in ('', 'localhost'):
                continue
            path = Path(unquote(url.path)).resolve()
            if not any(path.is_relative_to(root) for root in roots):
                continue
            item['path'] = str(path)
            item['abstract'] = item['abstract'][:2000]
            results.append(item)
            if len(results) >= limit:
                break
        conf['last_query_at'] = now()
        self.save()
        return {'source': 'recoll', 'results': results, 'limit': limit,
                'scope': 'authorized directories; bounded index result slice',
                'recorded_in_lac': False, 'queried_at': conf['last_query_at']}

    def activity(self, args):
        conf = self.config['activitywatch']
        if not conf['enabled']:
            raise ValueError('ActivityWatch integration is disabled')
        bucket = args.get('bucket', '')
        if not bucket or bucket not in conf['buckets'].splitlines():
            raise ValueError('Select an explicitly authorized bucket')
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=24)
        if args.get('start'):
            start = datetime.fromisoformat(args['start'].replace('Z', '+00:00'))
        if args.get('end'):
            end = datetime.fromisoformat(args['end'].replace('Z', '+00:00'))
        if start.tzinfo is None or end.tzinfo is None or not timedelta(0) < end - start <= timedelta(days=7):
            raise ValueError('Use timestamps with timezone and a period of at most seven days')
        limit = max(1, min(200, int(args.get('limit', 100))))
        params = urlencode({'start': start.isoformat(), 'end': end.isoformat(), 'limit': limit})
        events = get_json(conf['url'], '/api/0/buckets/' + quote(bucket, safe='') + '/events?' + params)
        if not isinstance(events, list):
            raise ValueError('Invalid events response')
        totals = {}
        # Return bounded aggregates to the UI and agents; omit titles, URLs and raw data.
        for event in events[:limit]:
            timestamp = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
            duration = float(event.get('duration', 0))
            if timestamp.tzinfo is None or not math.isfinite(duration) or duration < 0:
                raise ValueError('Invalid event timestamp or duration')
            duration = min(duration, 7 * 86400)
            clipped = max(0, (min(end, timestamp + timedelta(seconds=duration)) - max(start, timestamp)).total_seconds())
            app = str(event.get('data', {}).get('app', event.get('data', {}).get('status', 'unknown')))[:200]
            totals[app] = totals.get(app, 0) + clipped
        conf['last_query_at'] = now()
        self.save()
        return {'source': 'activitywatch', 'bucket': bucket, 'start': start.isoformat(), 'end': end.isoformat(),
                'events_returned': min(len(events), limit), 'possibly_truncated': len(events) >= limit,
                'applications': [{'app': app, 'seconds': seconds} for app, seconds in
                                 sorted(totals.items(), key=lambda pair: pair[1], reverse=True)],
                'interpretation': 'Reported intervals; no AFK correction, project attribution or productivity inference. Overlaps may exist.',
                'recorded_in_lac': False, 'queried_at': conf['last_query_at']}

    def dispatch(self, action, args):
        if action == 'status':
            return self.status()
        if action == 'configure':
            return self.configure(args)
        if action == 'search':
            return self.search(args)
        if action == 'activity':
            return self.activity(args)
        raise ValueError('Unknown integration action')


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--action', required=True)
    parser.add_argument('--params', default='')
    options = parser.parse_args()
    try:
        result = Adapters(options.config).dispatch(options.action, dict(parse_qsl(options.params, keep_blank_values=True)))
    except (OSError, ValueError, KeyError, TypeError, OverflowError, subprocess.SubprocessError, http.client.HTTPException) as exc:
        result = {'error': str(exc)}
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()
