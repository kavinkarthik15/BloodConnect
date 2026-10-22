type AsyncStateInput = {
  loading: boolean;
  error: string;
  hasData: boolean;
  loadingMessage: string;
  emptyMessage: string;
};

type AsyncStateResult = {
  kind: 'loading' | 'error' | 'empty' | 'content';
  message: string;
};

export function resolveAsyncState(input: AsyncStateInput): AsyncStateResult;
