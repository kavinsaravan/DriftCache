/**
 * Settings Page
 *
 * Configure cache behavior and system parameters
 */
import { useState } from 'react';
import { Save, AlertCircle, CheckCircle2, Settings as SettingsIcon } from 'lucide-react';

interface SettingsState {
  // Cache Configuration
  similarityThreshold: number;
  cacheTTL: number;
  maxCacheSize: number;

  // Provider Configuration
  defaultProvider: string;
  defaultModel: string;
  enableStreaming: boolean;

  // Analytics Configuration
  metricsRetention: number;
  enableDetailedLogging: boolean;

  // System Configuration
  redisURL: string;
  databaseURL: string;
}

export default function Settings() {
  const [settings, setSettings] = useState<SettingsState>({
    similarityThreshold: 0.85,
    cacheTTL: 3600,
    maxCacheSize: 10000,
    defaultProvider: 'openai',
    defaultModel: 'gpt-4',
    enableStreaming: true,
    metricsRetention: 30,
    enableDetailedLogging: true,
    redisURL: 'redis://localhost:6379',
    databaseURL: 'postgresql://localhost:5432/driftcache',
  });

  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle');

  const handleSave = async () => {
    setSaveStatus('saving');

    // Simulate API call
    setTimeout(() => {
      setSaveStatus('success');
      setTimeout(() => setSaveStatus('idle'), 3000);
    }, 1000);
  };

  const handleReset = () => {
    setSettings({
      similarityThreshold: 0.85,
      cacheTTL: 3600,
      maxCacheSize: 10000,
      defaultProvider: 'openai',
      defaultModel: 'gpt-4',
      enableStreaming: true,
      metricsRetention: 30,
      enableDetailedLogging: true,
      redisURL: 'redis://localhost:6379',
      databaseURL: 'postgresql://localhost:5432/driftcache',
    });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-600 mt-1">
          Configure cache behavior and system parameters
        </p>
      </div>

      {/* Save Status */}
      {saveStatus === 'success' && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-center">
          <CheckCircle2 className="w-5 h-5 text-green-600 mr-2" />
          <p className="text-green-800">Settings saved successfully!</p>
        </div>
      )}

      {saveStatus === 'error' && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center">
          <AlertCircle className="w-5 h-5 text-red-600 mr-2" />
          <p className="text-red-800">Failed to save settings. Please try again.</p>
        </div>
      )}

      {/* Cache Configuration */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center mb-4">
          <SettingsIcon className="w-5 h-5 text-blue-600 mr-2" />
          <h2 className="text-lg font-semibold text-gray-900">Cache Configuration</h2>
        </div>

        <div className="space-y-4">
          {/* Similarity Threshold */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Similarity Threshold
            </label>
            <div className="flex items-center space-x-4">
              <input
                type="range"
                min="0.5"
                max="1.0"
                step="0.01"
                value={settings.similarityThreshold}
                onChange={(e) =>
                  setSettings({ ...settings, similarityThreshold: parseFloat(e.target.value) })
                }
                className="flex-1"
              />
              <span className="text-sm font-medium text-gray-900 w-12">
                {settings.similarityThreshold.toFixed(2)}
              </span>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Higher values require closer matches for cache hits (recommended: 0.85)
            </p>
          </div>

          {/* Cache TTL */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Cache TTL (seconds)
            </label>
            <input
              type="number"
              value={settings.cacheTTL}
              onChange={(e) => setSettings({ ...settings, cacheTTL: parseInt(e.target.value) })}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="text-xs text-gray-500 mt-1">
              How long cached responses remain valid (default: 3600 = 1 hour)
            </p>
          </div>

          {/* Max Cache Size */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Max Cache Size (entries)
            </label>
            <input
              type="number"
              value={settings.maxCacheSize}
              onChange={(e) =>
                setSettings({ ...settings, maxCacheSize: parseInt(e.target.value) })
              }
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="text-xs text-gray-500 mt-1">
              Maximum number of cached entries before eviction (default: 10000)
            </p>
          </div>
        </div>
      </div>

      {/* Provider Configuration */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Provider Configuration</h2>

        <div className="space-y-4">
          {/* Default Provider */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Default Provider
            </label>
            <select
              value={settings.defaultProvider}
              onChange={(e) => setSettings({ ...settings, defaultProvider: e.target.value })}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
              <option value="cohere">Cohere</option>
              <option value="google">Google (Gemini)</option>
            </select>
          </div>

          {/* Default Model */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Default Model
            </label>
            <select
              value={settings.defaultModel}
              onChange={(e) => setSettings({ ...settings, defaultModel: e.target.value })}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="gpt-4">GPT-4</option>
              <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
              <option value="claude-3-opus">Claude 3 Opus</option>
              <option value="claude-3-sonnet">Claude 3 Sonnet</option>
              <option value="command-r-plus">Command R+</option>
              <option value="gemini-pro">Gemini Pro</option>
            </select>
          </div>

          {/* Enable Streaming */}
          <div className="flex items-center">
            <input
              type="checkbox"
              id="enableStreaming"
              checked={settings.enableStreaming}
              onChange={(e) => setSettings({ ...settings, enableStreaming: e.target.checked })}
              className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
            />
            <label htmlFor="enableStreaming" className="ml-2 text-sm font-medium text-gray-700">
              Enable streaming responses
            </label>
          </div>
        </div>
      </div>

      {/* Analytics Configuration */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Analytics Configuration</h2>

        <div className="space-y-4">
          {/* Metrics Retention */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Metrics Retention (days)
            </label>
            <input
              type="number"
              value={settings.metricsRetention}
              onChange={(e) =>
                setSettings({ ...settings, metricsRetention: parseInt(e.target.value) })
              }
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="text-xs text-gray-500 mt-1">
              How long to retain detailed metrics data (default: 30 days)
            </p>
          </div>

          {/* Enable Detailed Logging */}
          <div className="flex items-center">
            <input
              type="checkbox"
              id="enableDetailedLogging"
              checked={settings.enableDetailedLogging}
              onChange={(e) =>
                setSettings({ ...settings, enableDetailedLogging: e.target.checked })
              }
              className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
            />
            <label
              htmlFor="enableDetailedLogging"
              className="ml-2 text-sm font-medium text-gray-700"
            >
              Enable detailed request/response logging
            </label>
          </div>
        </div>
      </div>

      {/* System Configuration */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">System Configuration</h2>

        <div className="space-y-4">
          {/* Redis URL */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Redis URL</label>
            <input
              type="text"
              value={settings.redisURL}
              onChange={(e) => setSettings({ ...settings, redisURL: e.target.value })}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
            />
          </div>

          {/* Database URL */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              PostgreSQL Database URL
            </label>
            <input
              type="text"
              value={settings.databaseURL}
              onChange={(e) => setSettings({ ...settings, databaseURL: e.target.value })}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
            />
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between bg-white rounded-lg shadow p-6">
        <button
          onClick={handleReset}
          className="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50"
        >
          Reset to Defaults
        </button>

        <button
          onClick={handleSave}
          disabled={saveStatus === 'saving'}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:bg-blue-400 flex items-center"
        >
          {saveStatus === 'saving' ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
              Saving...
            </>
          ) : (
            <>
              <Save className="w-4 h-4 mr-2" />
              Save Changes
            </>
          )}
        </button>
      </div>

      {/* Information */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-start">
          <AlertCircle className="w-5 h-5 text-blue-600 mr-2 mt-0.5" />
          <div className="text-sm text-blue-800">
            <p className="font-medium mb-1">Important Notes:</p>
            <ul className="list-disc list-inside space-y-1">
              <li>Changes to similarity threshold affect future cache decisions only</li>
              <li>Modifying Redis or Database URLs requires application restart</li>
              <li>Cache TTL changes apply to new cache entries only</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
