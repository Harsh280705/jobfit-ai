import { useQuery } from '@tanstack/react-query';
import { fetchAnalysis } from '../services/api';

export function useAnalysis(id: string | undefined, enabled = true) {
  return useQuery({
    queryKey: ['analysis', id],
    queryFn: () => fetchAnalysis(id!),
    enabled: enabled && !!id,
    refetchInterval: (q) =>
      q.state.data?.status === 'COMPLETED' || q.state.data?.status === 'FAILED' ? false : 1500,
  });
}
