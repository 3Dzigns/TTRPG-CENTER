import { useMutation, useQuery } from 'react-query';

interface AskRequest {
  query: string;
  session_id?: string;
}

interface AskResponse {
  answer: string;
  session_id: string;
  confidence: number;
  sources: string[];
  processing_time_ms: number;
  classification?: any;
}

interface PlanRequest {
  request: string;
  session_id?: string;
  complexity_limit?: string;
}

interface PlanStep {
  step_id: string;
  description: string;
  estimated_duration_seconds: number;
  dependencies: string[];
  resources_required: string[];
}

interface PlanResponse {
  plan_id: string;
  session_id: string;
  steps: PlanStep[];
  total_estimated_duration_seconds: number;
  complexity: string;
  validated: boolean;
}

interface RunRequest {
  plan_id: string;
  session_id: string;
  execute_all?: boolean;
}

interface RunStatus {
  run_id: string;
  plan_id: string;
  session_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  current_step?: string;
  progress: number;
  results: Record<string, any>;
  started_at?: string;
  completed_at?: string;
}

const getApiUrl = (): string => {
  const currentEnv = import.meta.env.MODE || 'development';
  const portMap = {
    development: 8002,
    test: 8183,
    production: 8284
  };
  const port = portMap[currentEnv] || 8002;
  return `http://localhost:${port}`;
};

export const useUserAPI = () => {
  // Ask Query Mutation
  const askMutation = useMutation<AskResponse, Error, AskRequest>({
    mutationFn: async (request: AskRequest) => {
      const apiUrl = getApiUrl();
      const params = new URLSearchParams();
      params.append('query', request.query);
      if (request.session_id) params.append('session_id', request.session_id);

      const response = await fetch(`${apiUrl}/ask?${params.toString()}`);
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Ask request failed');
      }
      return response.json();
    }
  });

  // Plan Creation Mutation
  const planMutation = useMutation<PlanResponse, Error, PlanRequest>({
    mutationFn: async (request: PlanRequest) => {
      const apiUrl = getApiUrl();
      const params = new URLSearchParams();
      params.append('request', request.request);
      if (request.session_id) params.append('session_id', request.session_id);
      if (request.complexity_limit) params.append('complexity_limit', request.complexity_limit);

      const response = await fetch(`${apiUrl}/plan?${params.toString()}`);
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Plan creation failed');
      }
      return response.json();
    }
  });

  // Run Execution Mutation
  const runMutation = useMutation<RunStatus, Error, RunRequest>({
    mutationFn: async (request: RunRequest) => {
      const apiUrl = getApiUrl();
      const response = await fetch(`${apiUrl}/run`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request)
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Run execution failed');
      }
      return response.json();
    }
  });

  // Get Run Status Query
  const useRunStatus = (runId?: string) => {
    return useQuery<RunStatus, Error>(
      ['runStatus', runId],
      async () => {
        if (!runId) throw new Error('Run ID is required');
        const apiUrl = getApiUrl();
        const response = await fetch(`${apiUrl}/runs/${runId}`);
        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || 'Failed to get run status');
        }
        return response.json();
      },
      {
        enabled: !!runId,
        refetchInterval: 2000, // Poll every 2 seconds for active runs
        refetchIntervalInBackground: false
      }
    );
  };

  // Session Management
  const useSessionInfo = (sessionId?: string) => {
    return useQuery(
      ['session', sessionId],
      async () => {
        if (!sessionId) throw new Error('Session ID is required');
        const apiUrl = getApiUrl();
        const response = await fetch(`${apiUrl}/sessions/${sessionId}`);
        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || 'Failed to get session info');
        }
        return response.json();
      },
      {
        enabled: !!sessionId,
        staleTime: 30000 // 30 seconds
      }
    );
  };

  const clearSessionMutation = useMutation<void, Error, string>({
    mutationFn: async (sessionId: string) => {
      const apiUrl = getApiUrl();
      const response = await fetch(`${apiUrl}/sessions/${sessionId}`, {
        method: 'DELETE'
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to clear session');
      }
    }
  });

  return {
    // Ask functionality
    askQuery: askMutation.mutateAsync,
    askLoading: askMutation.isLoading,
    askError: askMutation.error,

    // Plan functionality
    createPlan: planMutation.mutateAsync,
    planLoading: planMutation.isLoading,
    planError: planMutation.error,

    // Run functionality
    executePlan: runMutation.mutateAsync,
    runLoading: runMutation.isLoading,
    runError: runMutation.error,

    // Status monitoring
    useRunStatus,

    // Session management
    useSessionInfo,
    clearSession: clearSessionMutation.mutateAsync,
    clearSessionLoading: clearSessionMutation.isLoading
  };
};