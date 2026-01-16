import axios from 'axios';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://127.0.0.1:8000/api';

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 60000, // 60 second timeout for chatbot (can take longer)
  headers: {
    'Content-Type': 'application/json',
  },
});

// Simple in-memory cache for API responses (reduces redundant calls)
const cache = new Map<string, { data: any; timestamp: number }>();
const CACHE_TTL = 30000; // 30 seconds cache

function getCached<T>(key: string): T | null {
  const cached = cache.get(key);
  if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
    return cached.data as T;
  }
  cache.delete(key);
  return null;
}

function setCache<T>(key: string, data: T): void {
  cache.set(key, { data, timestamp: Date.now() });
  // Clean old entries
  if (cache.size > 50) {
    const oldest = Array.from(cache.entries()).sort((a, b) => a[1].timestamp - b[1].timestamp)[0];
    if (oldest) cache.delete(oldest[0]);
  }
}

export function clearCache(): void {
  cache.clear();
}

// Add response interceptor for better error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.code === 'ECONNABORTED') {
      console.error('Request timed out');
    } else if (error.code === 'ERR_NETWORK' || error.message?.includes('Network Error')) {
      console.error('Network error - backend may not be running');
      error.message = 'Cannot connect to server. Please ensure the backend is running on http://127.0.0.1:8000';
    } else if (error.response) {
      console.error('API Error:', error.response.status, error.response.data);
    } else {
      console.error('Request Error:', error.message);
    }
    return Promise.reject(error);
  }
);


// Types
export interface BatchCreate {
  mode: 'aicte' | 'nba' | 'naac' | 'nirf';
  new_university?: boolean;
  institution_name?: string;
  department_name?: string;
  academic_year?: string;
}

export interface BatchResponse {
  batch_id: string;
  mode: string;
  status: string;
  created_at: string;
  updated_at: string;
  total_documents: number;
  processed_documents: number;
  institution_name: string | null;
  data_source?: 'user' | 'system';  // "user" = uploaded PDFs, "system" = pre-seeded historical data
}

export interface DocumentUploadResponse {
  document_id: string;
  filename: string;
  file_size: number;
  uploaded_at: string;
}

export interface ProcessingStatusResponse {
  batch_id: string;
  status: string;
  current_stage: string;
  progress: number;
  total_documents: number;
  processed_documents: number;
  errors: string[];
}

export interface KPICard {
  name: string;
  value: number | null;
  label: string;
  color: string;
}

export interface BlockCard {
  block_id: string;
  block_type: string;
  block_name: string;
  is_present: boolean;
  is_outdated: boolean;
  is_low_quality: boolean;
  is_invalid: boolean;
  confidence: number;
  extracted_fields_count: number;
  evidence_snippet?: string;
  evidence_page?: number;
  source_doc?: string;
}

export interface BlockWithData extends BlockCard {
  data: Record<string, unknown>;
}

export interface SufficiencyCard {
  percentage: number;
  present_count: number;
  required_count: number;
  missing_blocks: string[];
  penalty_breakdown: Record<string, number>;
  color: string;
}

export interface ComplianceFlag {
  severity: string;
  title: string;
  reason: string;
  evidence_page?: number;
  evidence_snippet?: string;
  recommendation?: string;
}

export interface TrendDataPoint {
  year: string;
  kpi_name: string;
  value: number;
}

export interface DashboardResponse {
  batch_id: string;
  mode: string;
  institution_name: string | null;
  kpi_cards: KPICard[];
  kpis: Record<string, number | null>;
  block_cards: BlockCard[];
  blocks: BlockWithData[];
  sufficiency: SufficiencyCard;
  compliance_flags: ComplianceFlag[];
  trend_data: TrendDataPoint[];
  total_documents: number;
  processed_documents: number;
  approval_classification?: ApprovalClassification | null;
  approval_readiness?: ApprovalReadiness | null;
  batch_status?: string;  // For invalid batch detection
  overall_score?: number | null;  // For invalid batch detection
}

export interface ChatMessage {
  batch_id: string;
  message: string;
}

export interface ChatResponse {
  response: string;
  sources: string[];
}

export interface ChatQueryRequest {
  query: string;
  batch_id?: string;  // Optional - for accreditation context
  current_page?: string;
  comparison_batch_ids?: string[];
}

export interface ChatQueryResponse {
  answer: string;
  citations: string[];
  related_blocks: string[];
  requires_context: boolean;
}

export interface ReportGenerateResponse {
  batch_id: string;
  report_path: string;
  download_url: string;
  generated_at: string;
}

export interface ApprovalClassification {
  category: string;
  subtype: string;
  signals: string[];
}

export interface ApprovalReadiness {
  approval_category: string;
  approval_readiness_score: number;
  present: number;
  required: number;
  approval_missing_documents: string[];
  recommendation: string;
}

export interface SkippedBatch {
  batch_id: string;
  reason: string;
}

export interface ComparisonInstitution {
  batch_id: string;
  institution_name: string;
  short_label: string;
  academic_year?: string | null;
  mode: string;
  kpis: Record<string, number | null>;
  sufficiency_percent: number;
  compliance_count: number;
  overall_score: number;
  strengths: string[];
  weaknesses: string[];
}

export interface CategoryWinner {
  kpi_key: string;
  kpi_name: string;
  winner_batch_id: string;
  winner_label: string;
  winner_value: number;
  is_tie: boolean;
  tied_with: string[];
}

export interface ComparisonInterpretation {
  best_overall_batch_id: string;
  best_overall_label: string;
  best_overall_name: string;
  category_winners: CategoryWinner[];
  notes: string[];
}

export interface ComparisonResponse {
  institutions: ComparisonInstitution[];
  skipped_batches: SkippedBatch[];
  comparison_matrix: Record<string, Record<string, number | null>>;
  winner_institution?: string | null;
  winner_label?: string | null;
  winner_name?: string | null;
  category_winners: Record<string, string>;
  category_winners_labels: Record<string, string>;
  interpretation?: ComparisonInterpretation | null;
  valid_for_comparison: boolean;
  validation_message?: string | null;
}

export interface RankingInstitution {
  batch_id: string;
  name: string;
  short_label: string;
  ranking_score: number;
  fsr_score: number | null;
  infrastructure_score: number | null;
  placement_index: number | null;
  lab_compliance_index: number | null;
  overall_score: number | null;
  mode: string;
  strengths: string[];
  weaknesses: string[];
}

export interface RankingResponse {
  ranking_type: string;
  top_n: number;
  institutions: RankingInstitution[];
  insufficient_batches: SkippedBatch[];
}



// API Functions
export const batchApi = {
  create: async (data: BatchCreate): Promise<BatchResponse> => {
    const response = await api.post<BatchResponse>('/batches/create', data);
    return response.data;
  },
  get: async (batchId: string): Promise<BatchResponse> => {
    const response = await api.get<BatchResponse>(`/batches/${batchId}`);
    return response.data;
  },
  list: async (): Promise<BatchResponse[]> => {
    const response = await api.get<BatchResponse[]>('/batches/list');
    return response.data;
  },
};

export const documentApi = {
  upload: async (batchId: string, file: File): Promise<DocumentUploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post<DocumentUploadResponse>(
      `/documents/${batchId}/upload`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },
};

export const processingApi = {
  start: async (batchId: string): Promise<{ batch_id: string; status: string; message: string }> => {
    const response = await api.post('/processing/start', { batch_id: batchId });
    return response.data;
  },
  getStatus: async (batchId: string): Promise<ProcessingStatusResponse> => {
    const response = await api.get<ProcessingStatusResponse>(`/processing/status/${batchId}`);
    return response.data;
  },
};

export interface Evaluation {
  batch_id: string;
  academic_year: string | null;
  mode: string;
  institution_name: string | null;
  department_name: string | null;
  overall_score: number | null;
  created_at: string | null;
  total_documents: number;
}

export const dashboardApi = {
  listEvaluations: async (params?: {
    academic_year?: string;
    mode?: string;
    department_name?: string;
  }): Promise<Evaluation[]> => {
    const queryParams = new URLSearchParams();
    if (params?.academic_year) queryParams.append('academic_year', params.academic_year);
    if (params?.mode) queryParams.append('mode', params.mode);
    if (params?.department_name) queryParams.append('department_name', params.department_name);

    const url = `/dashboard/evaluations${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
    const response = await api.get<Evaluation[]>(url);
    return response.data;
  },
  get: async (batchId: string): Promise<DashboardResponse> => {
    const response = await api.get<DashboardResponse>(`/dashboard/${batchId}`);
    return response.data;
  },
  getKpiDetails: async (batchId: string, kpiType: string): Promise<KPIDetailsResponse> => {
    // Backend endpoint: /api/dashboard/kpi-details/{batch_id}?kpi_type={kpi_type}
    const response = await api.get<KPIDetailsResponse>(`/dashboard/kpi-details/${batchId}`, {
      params: { kpi_type: kpiType }
    });
    return response.data;
  },
  getTrends: async (batchId: string): Promise<YearwiseTrendsResponse> => {
    const response = await api.get<YearwiseTrendsResponse>(`/dashboard/trends/${batchId}`);
    return response.data;
  },
  getForecast: async (batchId: string, kpiName: string): Promise<ForecastResponse> => {
    const response = await api.get<ForecastResponse>(`/dashboard/forecast/${batchId}/${kpiName}`);
    return response.data;
  },
};

// Yearwise Trends Types
export interface KPITrendInfo {
  slope: number;
  volatility: number;
  min?: number;
  max?: number;
  avg?: number;
  insight: string;
  data_points: number;
}

export interface YearwiseTrendsResponse {
  years_available: number[];
  kpis_per_year: Record<string, Record<string, number | null>>;
  trends: Record<string, KPITrendInfo>;
  has_historical_data: boolean;
}

// Forecast Types
export interface ForecastPoint {
  year: number;
  predicted_value: number;
  lower_bound: number;
  upper_bound: number;
  confidence?: number;
}

export interface ForecastResponse {
  has_forecast?: boolean;
  can_forecast?: boolean;
  insufficient_data?: boolean;
  insufficient_data_reason?: string | null;
  forecast: ForecastPoint[] | null;
  confidence_band?: number;
  explanation?: string | null;
  model_info?: {
    method: string;
    slope: number;
    intercept: number;
    r_squared: number;
    historical_points: number;
  };
}

// KPI Details Types
export interface ParameterBreakdown {
  parameter_name: string;
  display_name: string;
  raw_value: unknown;
  normalized_value: number | null;
  unit: string;
  weight: number;
  score: number;
  contribution: number;
  missing: boolean;
  note: string;
}

export interface FormulaStep {
  step_number: number;
  description: string;
  formula: string;
  result: number | null;
}

export interface KPIBreakdown {
  kpi_key: string;
  kpi_name: string;
  final_score: number;
  parameters: ParameterBreakdown[];
  formula_steps: FormulaStep[];
  formula_text: string;
  missing_parameters: string[];
  data_quality: string;
  confidence: number;
}

export interface KPIDetailsResponse {
  batch_id: string;
  institution_name: string;
  mode: string;
  fsr: KPIBreakdown | null;
  infrastructure: KPIBreakdown | null;
  placement: KPIBreakdown | null;
  lab_compliance: KPIBreakdown | null;
  overall: KPIBreakdown | null;
}

export const chatbotApi = {
  chat: async (batchId: string, message: string): Promise<ChatResponse> => {
    const response = await api.post<ChatResponse>('/chatbot/chat', {
      message,
      batch_id: batchId,
    });
    return response.data;
  },
  query: async (request: ChatQueryRequest): Promise<ChatQueryResponse> => {
    // Use longer timeout for chatbot queries
    const response = await api.post<ChatQueryResponse>('/chatbot/query', request, {
      timeout: 90000, // 90 seconds for chatbot (AI can take time)
    });
    return response.data;
  },
};

// GovEasy API removed - feature not needed

export const reportApi = {
  generate: async (batchId: string, reportType: string = 'standard'): Promise<ReportGenerateResponse> => {
    const response = await api.post<ReportGenerateResponse>('/reports/generate', {
      batch_id: batchId,
      include_evidence: true,
      include_trends: true,
      report_type: reportType,
    });
    return response.data;
  },
  download: async (batchId: string): Promise<Blob> => {
    const response = await api.get(`/reports/download/${batchId}`, {
      responseType: 'blob',
    });
    return response.data;
  },
};

export const compareApi = {
  get: async (batchIds: string[]): Promise<ComparisonResponse> => {
    const qs = batchIds.join(',');
    const response = await api.get<ComparisonResponse>(`/compare`, {
      params: { batch_ids: qs },
    });
    return response.data;
  },
  rank: async (
    batchIds: string[],
    kpi: string,
    topN: number,
    weights?: Record<string, number>
  ): Promise<RankingResponse> => {
    const params: Record<string, unknown> = {
      batch_ids: batchIds.join(','),
      kpi,
      top_n: topN,
    };

    if (weights && kpi === 'all') {
      params.weights = JSON.stringify(weights);
    }

    const response = await api.get<RankingResponse>('/compare/rank', { params });
    return response.data;
  },
};

// Additional Approval API types
export interface ApprovalApiClassification {
  category: string;
  subtype: string;
  signals: string[];
  confidence: number;
}

export interface DocumentStatus {
  document_key: string;
  document_name: string;
  present: boolean;
  confidence: number;
}

export interface ApprovalResponse {
  batch_id: string;
  mode: string;
  classification: ApprovalClassification;
  required_documents: string[];
  required_documents_readable: string[];
  documents_found: string[];
  missing_documents: string[];
  missing_documents_readable: string[];
  document_details: DocumentStatus[];
  readiness_score: number;
  recommendation: string;
  present: number;
  required: number;
}

export const approvalApi = {
  get: async (batchId: string): Promise<ApprovalResponse> => {
    const response = await api.get<ApprovalResponse>(`/approval/${batchId}`);
    return response.data;
  },
};

// Unified Report API types
export interface KPISummary {
  name: string;
  value: number | null;
  status: string;
}

export interface RegulatorSummary {
  regulator: string;
  overall_score: number | null;
  kpis: KPISummary[];
  sufficiency_percentage: number;
  compliance_flags_count: number;
  missing_documents: string[];
}

export interface UnifiedObservation {
  category: string;
  observation: string;
  severity: string;
}

export interface UnifiedReportResponse {
  batch_id: string;
  institution_name: string | null;
  generated_at: string;
  classification: Record<string, unknown>;
  institution_profile: Record<string, unknown>;
  aicte_summary: RegulatorSummary | null;
  ugc_summary: RegulatorSummary | null;
  unified_observations: UnifiedObservation[];
  consolidated_kpi_score: number;
  approval_readiness_score: number;
  final_recommendation: string;
  all_missing_documents: string[];
}

export const unifiedReportApi = {
  get: async (batchId: string): Promise<UnifiedReportResponse> => {
    const response = await api.get<UnifiedReportResponse>(`/unified-report/${batchId}`);
    return response.data;
  },
};

// Analytics types
export interface YearMetric {
  year: string;
  value: number | null;
}

export interface MetricTrend {
  metric_name: string;
  display_name: string;
  values: YearMetric[];
  average: number | null;
  min_value: number | null;
  max_value: number | null;
  trend_direction: string;
}

export interface MultiYearAnalyticsResponse {
  institution_name: string;
  batch_count: number;
  years_requested: number;
  available_years: string[];
  metrics: Record<string, YearMetric[]>;
  trend_summary: Record<string, MetricTrend>;
  best_year: string | null;
  worst_year: string | null;
  insights: string[];
}

export interface MetricPrediction {
  metric_name: string;
  display_name: string;
  historical_values: YearMetric[];
  predicted_values: YearMetric[];
  trend_direction: string;
  confidence: number;
  explanation: string;
}

export interface PredictionResponse {
  institution_name: string;
  historical_years: string[];
  prediction_years: string[];
  forecasts: Record<string, MetricPrediction>;
  growth_areas: string[];
  decline_warnings: string[];
  recommendations: string[];
  has_enough_data: boolean;
  error_message: string | null;
}

export const analyticsApi = {
  getMultiYear: async (batchIds: string[], years: number = 5): Promise<MultiYearAnalyticsResponse> => {
    const response = await api.get<MultiYearAnalyticsResponse>('/analytics/multi_year', {
      params: { batch_ids: batchIds.join(','), years }
    });
    return response.data;
  },
  predict: async (batchIds: string[], yearsToPredict: number = 5): Promise<PredictionResponse> => {
    const response = await api.post<PredictionResponse>('/analytics/predict', {
      batch_ids: batchIds,
      years_to_predict: yearsToPredict,
      metrics: ['fsr_score', 'infrastructure_score', 'placement_index', 'lab_compliance_index', 'overall_score']
    });
    return response.data;
  },
};

// KPI Details API
export interface KPIDetailedParameter {
  name: string;
  display_name: string;
  extracted: number | null;
  norm: number | string;
  weight: number;
  contrib: number;
  unit: string;
  missing: boolean;
  evidence: {
    snippet: string;
    page: number;
    source_doc: string;
  };
}

export interface KPIDetailedResponse {
  kpi_type: string;
  kpi_name: string;
  score: number | null;
  weightages: Record<string, number>;
  parameters: KPIDetailedParameter[];
  calculation_steps: Array<{
    step: number;
    description: string;
    formula: string;
    result: number | null;
  }>;
  formula: string;
  evidence: Record<string, unknown>;
  included_kpis?: string[];
  excluded_kpis?: string[];
}

export const kpiDetailsApi = {
  get: async (batchId: string, kpiType: string): Promise<KPIDetailedResponse> => {
    // Backend endpoint: /api/dashboard/kpi-details/{batch_id}?kpi_type={kpi_type}
    const response = await api.get<KPIDetailedResponse>(`/dashboard/kpi-details/${batchId}`, {
      params: { kpi_type: kpiType }
    });
    return response.data;
  },
};

export default api;


