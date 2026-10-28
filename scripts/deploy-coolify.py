#!/usr/bin/env python3
"""Pin the checked CI images and source commit, deploy, and wait for Coolify."""
import json
import os
import time
import urllib.error
import urllib.request


def main():
    base = os.environ['COOLIFY_URL'].rstrip('/') + '/api/v1'
    token = os.environ['COOLIFY_API_TOKEN']
    uuid = os.environ['COOLIFY_APPLICATION_UUID']
    sha = os.environ['GITHUB_SHA']
    images = {key: os.environ[key] for key in ('FGAS_API_IMAGE', 'FGAS_WEB_IMAGE')}
    if not token or not uuid or any(not value for value in images.values()):
        raise SystemExit('Missing Coolify deployment configuration')

    def api(method, path, payload=None):
        body = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(base + path, data=body, method=method, headers={
            'Authorization': 'Bearer ' + token,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            # Do not print response bodies: configuration endpoints can contain secrets.
            raise SystemExit(f'Coolify {method} {path} failed: HTTP {error.code}') from None
        except urllib.error.URLError:
            raise SystemExit(f'Coolify {method} {path} failed: connection error') from None

    api('PATCH', f'/applications/{uuid}/envs/bulk', {'data': [
        {'key': key, 'value': value, 'is_literal': True, 'is_preview': False,
         'is_runtime': True, 'is_buildtime': False}
        for key, value in images.items()
    ]})
    api('PATCH', f'/applications/{uuid}', {'git_commit_sha': sha})
    result = api('POST', '/deploy', {'uuid': uuid, 'force': False})
    deployment = result['deployments'][0]['deployment_uuid']
    print(f'Coolify deployment: {deployment}', flush=True)
    deadline = time.monotonic() + 900
    previous = None
    while time.monotonic() < deadline:
        status = api('GET', f'/deployments/{deployment}')['status']
        if status != previous:
            print(f'Deployment status: {status}', flush=True)
            previous = status
        if status == 'finished':
            return
        if status in ('failed', 'cancelled', 'canceled'):
            raise SystemExit(f'Coolify deployment {status}; inspect the deployment in Coolify')
        time.sleep(5)
    raise SystemExit('Timed out waiting for Coolify; check its deployment status before retrying')


if __name__ == '__main__':
    main()
