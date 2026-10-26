import { FormEvent, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { accountApi, accountError, API_BASE_URL, ApplicationKey, NewKey } from '../api/accountApi';
import { useAccount } from '../context/AccountContext';

export default function Applications() {
  const account = useAccount()!;
  const client = useQueryClient();
  const [mode, setMode] = useState('register');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [keyName, setKeyName] = useState('production');
  const [secret, setSecret] = useState<NewKey | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const projectId = account.projectId;
  const integrationUrl = new URL(API_BASE_URL, window.location.origin).toString().replace(/\/$/, '');
  const keys = useQuery<ApplicationKey[]>({
    queryKey: ['application-keys', account.user?.id, projectId], enabled: !!account.user && !!projectId,
    queryFn: async () => (await accountApi.get(`/projects/${projectId}/keys`)).data,
  });
  const run = async (action: () => Promise<void>) => {
    setBusy(true); setError('');
    try { await action(); } catch (err) { setError(accountError(err)); } finally { setBusy(false); }
  };
  const submitAuth = (event: FormEvent) => {
    event.preventDefault();
    void run(async () => { await account.authenticate(mode, email, password); setPassword(''); });
  };
  if (account.loading) return <p>Loading your account…</p>;
  if (!account.user) return <div className="max-w-md mx-auto bg-white border rounded-xl p-8 space-y-5">
    <h1 className="text-2xl font-bold">{mode === 'register' ? 'Create your account' : 'Sign in'}</h1>
    <p className="text-gray-600">Create keys for your AI applications and view their cache activity.</p>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    <form onSubmit={submitAuth} className="space-y-4">
      <label className="block">Email<input className="block border rounded p-2 w-full mt-1" type="email" autoComplete="email" required value={email} onChange={e => setEmail(e.target.value)} /></label>
      <label className="block">Password<input className="block border rounded p-2 w-full mt-1" type="password" autoComplete={mode === 'register' ? 'new-password' : 'current-password'} minLength={12} maxLength={256} required value={password} onChange={e => setPassword(e.target.value)} /></label>
      <p className="text-sm text-gray-500">Use at least 12 characters.</p>
      <button disabled={busy} className="bg-blue-600 text-white rounded px-4 py-2 disabled:opacity-50">{busy ? 'Please wait…' : mode === 'register' ? 'Create account' : 'Sign in'}</button>
    </form>
    <button type="button" className="text-blue-700" onClick={() => { setMode(mode === 'register' ? 'login' : 'register'); setError(''); }}>{mode === 'register' ? 'Already have an account? Sign in' : 'New here? Create an account'}</button>
  </div>;
  return <div className="max-w-4xl space-y-6">
    <h1 className="text-2xl font-bold">Your applications</h1>
    <p className="text-gray-600">Each application has its own keys, cache and request history.</p>
    {error && <p role="alert" className="bg-red-50 text-red-700 p-4 rounded">{error}</p>}
    {account.projectsError ? <p role="alert">{accountError(account.projectsError)}</p> : null}
    <form className="bg-white border rounded-xl p-6 flex gap-3 items-end" onSubmit={e => {
      e.preventDefault(); void run(async () => {
        const { data } = await accountApi.post<NewKey>('/projects', { name, key_name: 'production' });
        setSecret(data); setCopied(false); setName('');
        await client.invalidateQueries({queryKey: ['account-projects']}); account.selectProject(data.project_id);
      });
    }}>
      <label className="flex-1">Application name<input required maxLength={100} value={name} onChange={e => setName(e.target.value)} placeholder="My support assistant" className="block mt-1 border rounded px-3 py-2 w-full" /></label>
      <button disabled={busy} className="bg-blue-600 text-white rounded px-4 py-2 disabled:opacity-50">Create application</button>
    </form>
    {secret && <section className="bg-blue-50 border border-blue-200 rounded-xl p-6 space-y-3" aria-label="New API key">
      <h2 className="font-semibold">Save your new API key</h2>
      <p className="text-sm">Application: {account.projects.find(p => p.id === secret.project_id)?.name || secret.project_id}</p>
      <p>This key is shown only once. Store it securely in your application's server environment.</p>
      <code className="block break-all select-all bg-white rounded p-3">{secret.api_key}</code>
      <button className="text-blue-700 mr-5" onClick={() => void run(async () => { await navigator.clipboard.writeText(secret.api_key); setCopied(true); })}>{copied ? 'Copied' : 'Copy key'}</button>
      <button className="text-blue-700" onClick={() => setSecret(null)}>I saved it — dismiss</button>
    </section>}
    {account.projectsLoading && <p>Loading applications…</p>}
    {!account.projectsLoading && !account.projects.length && !account.projectsError && <p>Create your first application to get an API key.</p>}
    {!!projectId && <section className="bg-white border rounded-xl p-6 space-y-4">
      <h2 className="text-lg font-semibold">Keys for {account.projects.find(p => p.id === projectId)?.name}</h2>
      <form className="flex items-end gap-3" onSubmit={e => {
        e.preventDefault(); void run(async () => {
          const {data} = await accountApi.post<NewKey>(`/projects/${projectId}/keys`, {name: keyName});
          setSecret(data); setCopied(false); await keys.refetch();
        });
      }}>
        <label>Key name<input required maxLength={100} className="block border rounded p-2 mt-1" value={keyName} onChange={e => setKeyName(e.target.value)} /></label>
        <button disabled={busy} className="bg-blue-600 text-white rounded px-4 py-2 disabled:opacity-50">Create key</button>
      </form>
      {keys.error ? <p role="alert">{accountError(keys.error)}</p> : null}
      {keys.isLoading && <p>Loading keys…</p>}
      <ul className="divide-y">{keys.data?.map(key => <li key={key.id} className="py-3 flex items-center gap-4">
        <span className="flex-1">{key.name} <code className="text-gray-500 ml-2">{key.key_prefix}…</code></span>
        {key.is_active ? <button disabled={busy} className="text-red-700" onClick={() => {
          if (!window.confirm(`Revoke ${key.name}? Applications using it will lose access.`)) return;
          void run(async () => {
            await accountApi.delete(`/projects/${projectId}/keys/${key.id}`);
            if (secret?.api_key.startsWith(key.key_prefix)) setSecret(null);
            await keys.refetch();
          });
        }}>Revoke</button> : <span className="text-gray-500">Revoked</span>}
      </li>)}</ul>
      <h2 className="font-semibold">Connect your AI application</h2>
      <p>Send requests through DriftCache using your new project key. Activity appears in the <Link className="text-blue-700" to="/">dashboard</Link> for the selected application.</p>
      <pre className="bg-gray-50 rounded p-4 overflow-auto text-sm">{`from openai import OpenAI\nimport os\n\nclient = OpenAI(\n    base_url="${integrationUrl}",\n    api_key=os.environ["DRIFTCACHE_API_KEY"],\n)\n\nresponse = client.chat.completions.create(\n    model="gpt-4o-mini",\n    messages=[{"role": "user", "content": "Hello!"}],\n)`}</pre>
      <p className="text-sm text-gray-600">Set DRIFTCACHE_API_KEY on your application's server. The model must be supported by the provider configured on your DriftCache backend.</p>
    </section>}
  </div>;
}
