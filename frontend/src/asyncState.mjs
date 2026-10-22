export function resolveAsyncState({ loading, error, hasData, loadingMessage, emptyMessage }) {
  if (loading) {
    return { kind: 'loading', message: loadingMessage };
  }

  if (error) {
    return { kind: 'error', message: error };
  }

  if (!hasData) {
    return { kind: 'empty', message: emptyMessage };
  }

  return { kind: 'content', message: '' };
}
