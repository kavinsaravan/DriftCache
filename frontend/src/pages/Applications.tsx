import { FormEvent, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { API_BASE_URL, CreatedWorkspace, IntegrationConfiguration, NewKey, WorkspaceKey, workspaceApi, workspaceError } from '../api/workspaceApi';
import { useWorkspace } from '../context/workspaceState';

export default function Applications() {
  const connection = useWorkspace()!;
  const workspace = connection.workspace;
  const [name, setName] = useState('');
  const [credential, setCredential] = useState('');
  const [keyName, setKeyName] = useState('production');
  const [secret, setSecret] = useState<NewKey | null>(null);
  const [created, setCreated] = useState<CreatedWorkspace | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const integrationUrl = new URL(API_BASE_URL, window.location.origin).toString().replace(/\/$/, '');
  const keys = useQuery<WorkspaceKey[]>({
    queryKey: ['workspace-keys', workspace?.id], enabled: !!workspace,
    queryFn: async () => (await workspaceApi.get('/current/keys')).data,
  });
  const integration = useQuery<IntegrationConfiguration>({
    queryKey: ['integration-configuration', workspace?.id], enabled: !!workspace,
    queryFn: async () => (await workspaceApi.get('/integration')).data,
  });
  const run = async (action: () => Promise<void>) => {
    setBusy(true); setError('');
    try { await action(); } catch (err) { setError(workspaceError(err)); } finally { setBusy(false); }
  };
  const connect = (event: FormEvent) => {
    event.preventDefault();
    void run(async () => { await connection.connect(credential); setCredential(''); setSecret(null); setCreated(null); });
  };
  const shownKey = created?.api_key || secret?.api_key;
  const keyCard = shownKey && <section className="bg-blue-50 border border-blue-200 rounded-xl p-6 space-y-3" aria-label="New API key">
    <h2 className="font-semibold">Save your workspace API key</h2>
    <p>This key is shown only once. It gives access to this workspace's data and key management. Save it securely; there is no email or password recovery.</p>
    <code className="block break-all select-all bg-white rounded p-3">{shownKey}</code>
    <button className="text-blue-700 mr-5" onClick={() => void run(async () => { await navigator.clipboard.writeText(shownKey); setCopied(true); })}>{copied ? 'Copied' : 'Copy key'}</button>
    <button className="text-blue-700" onClick={() => {
      if (created) connection.connectCreated(created);
      setCreated(null); setSecret(null);
    }}>{created ? 'I saved it — open workspace' : 'I saved it — dismiss'}</button>
  </section>;
  if (connection.loading) return <p>Loading your workspace…</p>;
  if (!workspace) return <div className="max-w-3xl mx-auto space-y-6">
    <h1 className="text-2xl font-bold">Your DriftCache workspace</h1>
    <p className="text-gray-600">Create a private workspace or connect with an existing key. No email or password needed.</p>
    {(error || connection.error) && <p role="alert" className="text-red-700">{error || connection.error}</p>}
    {keyCard}
    {!created && <form className="bg-white border rounded-xl p-6 space-y-4" onSubmit={e => {
      e.preventDefault(); void run(async () => {
        const {data} = await workspaceApi.post<CreatedWorkspace>('', {name, key_name: 'default'});
        setCreated(data); setCopied(false); setName('');
      });
    }}>
      <h2 className="text-lg font-semibold">Create my workspace</h2>
      <label className="block">Workspace name<input required maxLength={100} className="block border rounded p-2 w-full mt-1" value={name} onChange={e => setName(e.target.value)} placeholder="My support assistant" /></label>
      <p className="text-sm text-gray-500">The name is a label. Only the generated key grants access.</p>
      <button disabled={busy} className="bg-blue-600 text-white rounded px-4 py-2 disabled:opacity-50">Create workspace</button>
    </form>}
    {!created && <form onSubmit={connect} className="bg-white border rounded-xl p-6 space-y-4">
      <h2 className="text-lg font-semibold">Connect with key</h2>
      <label className="block">Workspace API key<input required type="password" autoComplete="off" className="block border rounded p-2 w-full mt-1" value={credential} onChange={e => setCredential(e.target.value)} placeholder="dc_live_…" /></label>
      <button disabled={busy} className="bg-blue-600 text-white rounded px-4 py-2 disabled:opacity-50">Connect workspace</button>
    </form>}
  </div>;
  return <div className="max-w-4xl space-y-6">
    <h1 className="text-2xl font-bold">{workspace.name}</h1>
    <p className="text-gray-600">Use this workspace's keys in your AI applications. Its cache, metrics and request history are isolated from other workspaces.</p>
    {error && <p role="alert" className="bg-red-50 text-red-700 p-4 rounded">{error}</p>}
    {keyCard}
    <section className="bg-white border rounded-xl p-6 space-y-4">
      <h2 className="text-lg font-semibold">Workspace keys</h2>
      <form className="flex items-end gap-3" onSubmit={e => {
        e.preventDefault(); void run(async () => {
          const {data} = await workspaceApi.post<NewKey>('/current/keys', {name: keyName});
          setSecret(data); setCopied(false); await keys.refetch();
        });
      }}>
        <label>Key name<input required maxLength={100} className="block border rounded p-2 mt-1" value={keyName} onChange={e => setKeyName(e.target.value)} /></label>
        <button disabled={busy} className="bg-blue-600 text-white rounded px-4 py-2 disabled:opacity-50">Create key</button>
      </form>
      <p className="text-sm text-gray-600">To rotate your connection key, save a new key, disconnect, connect with the new key, then revoke the old one.</p>
      {keys.error ? <p role="alert">{workspaceError(keys.error)}</p> : null}
      {keys.isLoading && <p>Loading keys…</p>}
      <ul className="divide-y">{keys.data?.map(key => <li key={key.id} className="py-3 flex items-center gap-4">
        <span className="flex-1">{key.name} <code className="text-gray-500 ml-2">{key.key_prefix}…</code></span>
        {key.is_active ? <button disabled={busy} className="text-red-700" onClick={() => {
          if (!window.confirm(`Revoke ${key.name}? Applications using it will lose access.`)) return;
          void run(async () => {
            await workspaceApi.delete(`/current/keys/${key.id}`);
            if (secret?.api_key.startsWith(key.key_prefix)) setSecret(null);
            await keys.refetch();
          });
        }}>Revoke</button> : <span className="text-gray-500">Revoked</span>}
      </li>)}</ul>
    </section>
    <section className="bg-white border rounded-xl p-6 space-y-4">
      <h2 className="font-semibold">Connect your AI application</h2>
      <p>Send requests through DriftCache using this workspace's API key, then view its <Link className="text-blue-700" to="/">dashboard</Link>.</p>
      {integration.isLoading && <p>Loading connection settings…</p>}
      {integration.error && <div role="alert" className="text-red-700"><p>Unable to load connection settings. {workspaceError(integration.error)}</p>
        <button className="text-blue-700" onClick={() => void integration.refetch()}>Retry connection settings</button></div>}
      {integration.data && !integration.data.configured && <p role="alert" className="text-amber-800">The backend's default model has no configured provider. Contact the DriftCache operator to finish setup.</p>}
      {integration.data?.configured && <>
        <p>Provider: {integration.data.default_provider} · Model: {integration.data.default_model}</p>
        <pre className="bg-gray-50 rounded p-4 overflow-auto text-sm">{`from openai import OpenAI\nimport os\n\nclient = OpenAI(\n    base_url="${integrationUrl}",\n    api_key=os.environ["DRIFTCACHE_API_KEY"],\n)\n\nresponse = client.chat.completions.create(\n    model=${JSON.stringify(integration.data.default_model)},\n    messages=[{"role": "user", "content": "Hello!"}],\n)`}</pre>
        <p className="text-sm text-gray-600">Store DRIFTCACHE_API_KEY on your application's server. The upstream AI provider is configured by the DriftCache operator.</p>
      </>}
    </section>
  </div>;
}
