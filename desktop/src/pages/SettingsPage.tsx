/**
 * Settings: which server this console talks to, plus build information.
 */
import { useEffect, useState, type FormEvent } from 'react';

import { applyBaseUrl } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { useToast } from '../components/Toast';
import { Badge, Button, Field, Panel, TextInput } from '../components/ui';
import { bridge, isElectron } from '../lib/bridge';

export function SettingsPage() {
  const toast = useToast();
  const { user } = useAuth();
  const [apiBaseUrl, setApiBaseUrl] = useState('');
  const [saving, setSaving] = useState(false);
  const [info, setInfo] = useState<{
    version: string;
    platform: string;
    encryptionAvailable: boolean;
  } | null>(null);

  useEffect(() => {
    void (async () => {
      const [settings, appInfo] = await Promise.all([
        bridge().settings.get(),
        bridge().app.info(),
      ]);
      setApiBaseUrl(settings.apiBaseUrl);
      setInfo(appInfo);
    })();
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    try {
      const accepted = await bridge().settings.setApiBaseUrl(apiBaseUrl.trim());
      if (!accepted) {
        toast.error('Enter a valid http:// or https:// address.');
        return;
      }
      await applyBaseUrl();
      toast.success('Server address saved.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <Panel title="Server" description="Where this console sends its requests.">
        <form onSubmit={onSubmit} className="flex flex-col gap-4 px-5 py-5">
          <Field
            label="API base URL"
            htmlFor="api-url"
            hint="For example http://127.0.0.1:8000/api/v1"
          >
            <TextInput
              id="api-url"
              value={apiBaseUrl}
              onChange={(event) => setApiBaseUrl(event.target.value)}
              placeholder="http://127.0.0.1:8000/api/v1"
            />
          </Field>
          <div>
            <Button type="submit" loading={saving}>
              Save server address
            </Button>
          </div>
        </form>
      </Panel>

      <Panel title="Signed in as">
        <dl className="divide-y divide-shell-200">
          {[
            ['Name', user?.full_name ?? '—'],
            ['Email', user?.email ?? '—'],
            ['Role', user?.role.name ?? '—'],
          ].map(([term, value]) => (
            <div key={term} className="flex items-center justify-between px-5 py-3">
              <dt className="text-sm text-shell-600">{term}</dt>
              <dd className="text-sm font-medium text-shell-900">{value}</dd>
            </div>
          ))}
        </dl>
      </Panel>

      <Panel title="Application">
        <dl className="divide-y divide-shell-200">
          <div className="flex items-center justify-between px-5 py-3">
            <dt className="text-sm text-shell-600">Version</dt>
            <dd className="text-sm font-medium text-shell-900">{info?.version ?? '—'}</dd>
          </div>
          <div className="flex items-center justify-between px-5 py-3">
            <dt className="text-sm text-shell-600">Platform</dt>
            <dd className="text-sm font-medium text-shell-900">{info?.platform ?? '—'}</dd>
          </div>
          <div className="flex items-center justify-between gap-4 px-5 py-3">
            <div>
              <dt className="text-sm text-shell-600">Credential storage</dt>
              <dd className="mt-0.5 text-xs text-shell-500">
                {isElectron()
                  ? info?.encryptionAvailable
                    ? 'Your sign-in token is encrypted by the operating system keychain.'
                    : 'No OS keychain is available on this machine, so the token is stored unencrypted. Avoid using production credentials here.'
                  : 'Running in a browser for development. Tokens are held in session storage only.'}
              </dd>
            </div>
            {isElectron() && info ? (
              info.encryptionAvailable ? (
                <Badge tone="success">Encrypted</Badge>
              ) : (
                <Badge tone="warning">Unencrypted</Badge>
              )
            ) : (
              <Badge tone="neutral">Dev</Badge>
            )}
          </div>
        </dl>
      </Panel>
    </div>
  );
}
