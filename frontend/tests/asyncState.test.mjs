import assert from 'node:assert/strict';
import test from 'node:test';

import { resolveAsyncState } from '../src/asyncState.mjs';

const messages = {
  loadingMessage: 'Loading requests...',
  emptyMessage: 'No requests have been created yet.',
};

test('loading state takes precedence while a request is in flight', () => {
  assert.deepEqual(
    resolveAsyncState({ loading: true, error: '', hasData: false, ...messages }),
    { kind: 'loading', message: 'Loading requests...' },
  );
});

test('successful empty response renders the empty state', () => {
  assert.deepEqual(
    resolveAsyncState({ loading: false, error: '', hasData: false, ...messages }),
    { kind: 'empty', message: 'No requests have been created yet.' },
  );
});

test('API failure renders an explicit error instead of an empty state', () => {
  assert.deepEqual(
    resolveAsyncState({
      loading: false,
      error: 'Unable to load requests. Please try again.',
      hasData: false,
      ...messages,
    }),
    { kind: 'error', message: 'Unable to load requests. Please try again.' },
  );
});

test('successful response with data renders content', () => {
  assert.deepEqual(
    resolveAsyncState({ loading: false, error: '', hasData: true, ...messages }),
    { kind: 'content', message: '' },
  );
});
