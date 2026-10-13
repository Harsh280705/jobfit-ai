import axios from 'axios';
import type {
  AnalysisDetail,
  AnalysisSummary,
  EvaluationResponse,
  GapAnalysisResponse,
  RequirementDetailResponse,
} from '../types';

const baseURL = (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export const api = axios.create({ baseURL });

interface IdResponse {
  id: string;
}

interface AnalysisCreateResponse {
  analysis_id: string;
  status: string;
}

export async function createResumeText(text: string): Promise<IdResponse> {
  const { data } = await api.post('/resumes', { text });
  return data;
}
export async function createJobText(title: string, text: string): Promise<IdResponse> {
  const { data } = await api.post('/jobs', { title, text });
  return data;
}
export async function uploadDocument(
  file: File,
  documentType: 'resume' | 'job_description',
): Promise<IdResponse & { document_type: string; filename: string; mime_type: string }> {
  const form = new FormData();
  form.append('file', file);
  form.append('document_type', documentType);
  const { data } = await api.post('/documents/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}
export async function fetchDocumentText(docId: string): Promise<string> {
  const { data } = await api.get<{ text?: string }>(`/documents/${docId}`);
  return data.text || '';
}
export async function createAnalysis(resume_id: string, job_description_id: string): Promise<AnalysisCreateResponse> {
  const { data } = await api.post('/analyses', { resume_id, job_description_id });
  return data;
}
export async function fetchAnalyses(): Promise<AnalysisSummary[]> {
  const { data } = await api.get('/analyses');
  return data;
}
export async function fetchAnalysis(id: string): Promise<AnalysisDetail> {
  const { data } = await api.get(`/analyses/${id}`);
  return data;
}
export async function fetchRequirementDetail(analysisId: string, reqId: string): Promise<RequirementDetailResponse> {
  const { data } = await api.get(`/analyses/${analysisId}/requirements/${reqId}`);
  return data;
}
export async function runEvaluation(): Promise<EvaluationResponse> {
  const { data } = await api.post('/evaluation/run', {});
  return data;
}
export async function fetchGapAnalysis(analysisId: string): Promise<GapAnalysisResponse> {
  const { data } = await api.post(`/analyses/${analysisId}/gap-analysis`, {});
  return data;
}
