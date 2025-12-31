import axios, { AxiosError } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

// Error code to user-friendly message mapping
const ERROR_MESSAGES: Record<string, string> = {
    // Document Processing (SXL-1XX)
    'SXL-101': 'Document not found. Please try uploading again.',
    'SXL-102': 'Invalid document format. Please upload a PDF file.',
    'SXL-103': 'Document upload failed. Please try again.',
    'SXL-104': 'Unable to process this document. The file may be corrupted.',
    // Table Extraction (SXL-2XX)
    'SXL-201': 'No tables found in the document. Please ensure it contains financial data.',
    'SXL-202': 'Unable to extract data from the PDF. Please check the document quality.',
    // Mapping (SXL-3XX)
    'SXL-301': 'Mapping not found. Please try again.',
    'SXL-302': 'Invalid mapping configuration.',
    // Template (SXL-4XX)
    'SXL-401': 'Template not found. Please select a different template.',
    'SXL-402': 'Invalid template format.',
    'SXL-403': 'Template processing failed.',
    // Authentication (SXL-5XX)
    'SXL-501': 'Invalid email or password. Please try again.',
    'SXL-502': 'Session expired. Please log in again.',
    'SXL-503': 'Account locked. Please contact support.',
    // Authorization (SXL-6XX)
    'SXL-601': 'You do not have permission to perform this action.',
    'SXL-602': 'Access denied.',
    // Validation (SXL-7XX)
    'SXL-701': 'Please check your input and try again.',
    'SXL-702': 'Please enter a valid email address.',
    'SXL-703': 'Password must be at least 8 characters.',
    // Database (SXL-8XX)
    'SXL-801': 'A database error occurred. Please try again later.',
    // External Services (SXL-9XX)
    'SXL-901': 'Service temporarily unavailable. Please try again later.',
};

// API Error interface
export interface ApiError {
    message: string;
    error_code?: string;
    details?: Record<string, unknown>;
}

// Parse error response and return user-friendly message
export const getErrorMessage = (error: unknown): string => {
    if (axios.isAxiosError(error)) {
        const axiosError = error as AxiosError<ApiError>;

        // Check for network errors
        if (!axiosError.response) {
            if (axiosError.code === 'ECONNABORTED') {
                return 'Request timed out. Please check your connection and try again.';
            }
            return 'Unable to connect to the server. Please check your internet connection.';
        }

        // Check for backend error code
        const errorCode = axiosError.response.data?.error_code;
        if (errorCode && ERROR_MESSAGES[errorCode]) {
            return ERROR_MESSAGES[errorCode];
        }

        // Check for detail message from FastAPI
        const detail = axiosError.response.data?.message ||
            (axiosError.response.data as unknown as { detail?: string })?.detail;
        if (detail && typeof detail === 'string') {
            return detail;
        }

        // HTTP status code fallback
        switch (axiosError.response.status) {
            case 400:
                return 'Invalid request. Please check your input.';
            case 401:
                return 'Please log in to continue.';
            case 403:
                return 'You do not have permission to perform this action.';
            case 404:
                return 'The requested resource was not found.';
            case 413:
                return 'File too large. Please upload a smaller file.';
            case 422:
                return 'Invalid data format. Please check your input.';
            case 429:
                return 'Too many requests. Please wait a moment and try again.';
            case 500:
                return 'Server error. Please try again later.';
            case 503:
                return 'Service temporarily unavailable. Please try again later.';
            default:
                return 'An unexpected error occurred. Please try again.';
        }
    }

    // Generic error
    if (error instanceof Error) {
        return error.message;
    }

    return 'An unexpected error occurred. Please try again.';
};

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
    timeout: 60000, // 60 second timeout
});

// Request interceptor - add auth token if available
api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('access_token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

// Response interceptor - handle common errors
api.interceptors.response.use(
    (response) => response,
    (error: AxiosError) => {
        // Handle 401 - redirect to login
        if (error.response?.status === 401) {
            // Only redirect if not already on login page
            if (!window.location.pathname.includes('/login')) {
                localStorage.removeItem('access_token');
                localStorage.removeItem('refresh_token');
                // Optionally redirect to login
                // window.location.href = '/login';
            }
        }

        // Log errors in development
        if (import.meta.env.DEV) {
            console.error('API Error:', {
                url: error.config?.url,
                method: error.config?.method,
                status: error.response?.status,
                data: error.response?.data,
            });
        }

        return Promise.reject(error);
    }
);

// API Response Types - Exported for use in components
export interface UploadResponse {
    document_id: string;
    filename: string;
    status: string;
    page_count?: number;
    tables?: TableResponse[];
    processing_time_ms?: number;
    created_at?: string;
}

export interface DocumentResponse {
    id: string;
    filename: string;
    status: string;
    created_at: string;
    page_count?: number;
    error_message?: string;
}

export interface ClassificationResult {
    text: string;
    label: string;
    confidence: number;
}

export interface TemplateResponse {
    template_id: string;
    name: string;
    filename?: string;
    sheet_count?: number;
    structure?: {
        sections?: unknown[];
        [key: string]: unknown;
    };
}

export interface TemplateGraphResponse {
    nodes: unknown[];
    edges: unknown[];
}

export interface ExtractedItem {
    id: string;
    text: string;
    value?: number;
}

export interface TemplateTarget {
    id: string;
    label: string;
    path: string;
}

export interface MappingResponse {
    mapping_id: string;
    status: string;
    mappings: MappingItem[];
    total_items?: number;
    mapped_count?: number;
    auto_mapped_count?: number;
    conflict_count?: number;
    average_confidence?: number;
}

export interface MappingItem {
    source_id: string;
    target_id: string;
    confidence: number;
    [key: string]: unknown;
}

export interface Conflict {
    id: string;
    conflict_type: string;
    severity: 'critical' | 'high' | 'medium' | 'low';
    description: string;
    source_label?: string;
    target_address?: string;
    suggestions: string[];
    is_resolved: boolean;
}

export interface ConflictResponse {
    conflicts: Conflict[];
}

export interface ResolveConflictResponse {
    success: boolean;
    conflict_id: string;
}

export interface CellData {
    value: string;
    parsed_value?: number;
    confidence: number;
    is_numeric?: boolean;
    reasoning?: string;
    bbox?: number[];
}

export interface TableRow {
    cells: CellData[];
}

export interface ExtractedTable {
    page: number;
    title: string;
    rows: TableRow[];
    confidence: number;
}

export interface TableResponse {
    page: number;
    rows: TableRow[];
    confidence?: number;
    detection_method?: string;
}

export interface ExtractionResponse {
    document_id?: string;
    filename?: string;
    tables: ExtractedTable[];
    total_tables?: number;
}

export interface AuditEntry {
    id: string;
    timestamp: string;
    action: string;
    resource_type: string;
    resource_id?: string;
    user_id?: string;
    details?: string;
    old_value?: string;
    new_value?: string;
}

export interface AuditLogResponse {
    entries: AuditEntry[];
    total: number;
    page: number;
    page_size: number;
    has_more: boolean;
}

export interface AuthTokenResponse {
    access_token: string;
    refresh_token: string;
    token_type: string;
}

export interface UserResponse {
    id: string;
    email: string;
    full_name?: string;
    role: string;
    is_active: boolean;
}

export interface LogoutResponse {
    message: string;
}


// Document APIs
export const uploadDocument = async (file: File): Promise<UploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post('/upload', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
    return response.data;
};

export const getDocument = async (documentId: string): Promise<DocumentResponse> => {
    const response = await api.get(`/documents/${documentId}`);
    return response.data;
};

// Classification APIs
export const classifyItem = async (text: string): Promise<ClassificationResult> => {
    const response = await api.post('/classify', { text });
    return response.data;
};

export const classifyBatch = async (texts: string[]): Promise<ClassificationResult[]> => {
    const response = await api.post('/classify/batch', { texts });
    return response.data;
};

// Template APIs
export const uploadTemplate = async (file: File): Promise<TemplateResponse> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post('/template/upload', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
    return response.data;
};

export const getTemplate = async (templateId: string): Promise<TemplateResponse> => {
    const response = await api.get(`/template/${templateId}`);
    return response.data;
};

export const getTemplateGraph = async (templateId: string, format: string = 'json'): Promise<TemplateGraphResponse> => {
    const response = await api.get(`/template/${templateId}/graph?format=${format}`);
    return response.data;
};

// Mapping APIs
export const createMapping = async (data: {
    extracted_items: ExtractedItem[];
    template_targets: TemplateTarget[];
    period?: string;
}): Promise<MappingResponse> => {
    const response = await api.post('/map', data);
    return response.data;
};

export const getMapping = async (mappingId: string): Promise<MappingResponse> => {
    const response = await api.get(`/mapping/${mappingId}`);
    return response.data;
};

export const getMappingConflicts = async (mappingId: string): Promise<ConflictResponse> => {
    const response = await api.get(`/mapping/${mappingId}/conflicts`);
    return response.data;
};

export const resolveConflict = async (
    mappingId: string,
    conflictId: string,
    resolution: string
): Promise<ResolveConflictResponse> => {
    const response = await api.put(`/mapping/${mappingId}/conflicts/${conflictId}/resolve`, {
        conflict_id: conflictId,
        resolution,
    });
    return response.data;
};

// Extraction APIs
export const getDocumentExtractions = async (documentId: string): Promise<ExtractionResponse> => {
    const response = await api.get(`/documents/${documentId}/extractions`);
    return response.data;
};

export const updateExtractionCell = async (
    documentId: string,
    pageIndex: number,
    rowIndex: number,
    columnIndex: number,
    reasoning?: string,
    value?: string
): Promise<{ success: boolean; message: string }> => {
    const response = await api.patch(`/documents/${documentId}/extractions/cell`, {
        page_index: pageIndex,
        row_index: rowIndex,
        column_index: columnIndex,
        reasoning,
        value,
    });
    return response.data;
};

// Audit APIs
export const getAuditLog = async (
    page: number = 1,
    pageSize: number = 20,
    resourceType?: string,
    action?: string
): Promise<AuditLogResponse> => {
    const params = new URLSearchParams();
    params.append('page', page.toString());
    params.append('page_size', pageSize.toString());
    if (resourceType) params.append('resource_type', resourceType);
    if (action) params.append('action', action);

    const response = await api.get(`/audit?${params.toString()}`);
    return response.data;
};

// Authentication APIs
export const register = async (email: string, password: string, fullName?: string): Promise<AuthTokenResponse> => {
    const response = await api.post('/auth/register', { email, password, full_name: fullName });
    return response.data;
};

export const login = async (email: string, password: string): Promise<AuthTokenResponse> => {
    const response = await api.post('/auth/login', { email, password });
    return response.data;
};

export const refreshToken = async (refreshTokenStr: string): Promise<AuthTokenResponse> => {
    const response = await api.post('/auth/refresh', { refresh_token: refreshTokenStr });
    return response.data;
};

export const getCurrentUser = async (): Promise<UserResponse> => {
    const response = await api.get('/auth/me');
    return response.data;
};

export const logout = async (): Promise<LogoutResponse> => {
    const response = await api.post('/auth/logout');
    return response.data;
};

// Add auth token to requests
export const setAuthToken = (token: string | null) => {
    if (token) {
        api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    } else {
        delete api.defaults.headers.common['Authorization'];
    }
};

// Export API Types
export interface StyleInfo {
    id: string;
    name: string;
    description: string;
}

export interface ColorwayInfo {
    id: string;
    name: string;
    primary_color: string;
}

export interface ExportOptionsResponse {
    styles: StyleInfo[];
    colorways: ColorwayInfo[];
    statement_types: string[];
}

export interface ExportRequest {
    document_id: string;
    statement_type: 'auto' | 'income_statement' | 'balance_sheet' | 'cash_flow';
    style: 'basic' | 'corporate' | 'professional';
    colorway: string;
    company_name?: string;
}

export interface ExportResponse {
    export_id: string;
    filename: string;
    download_url: string;
    style: string;
    colorway: string;
    periods: number[];
    rows_populated: number;
}

export interface ExportPreviewResponse {
    structure: {
        sections?: unknown[];
        [key: string]: unknown;
    };
    aggregated_data: {
        [category: string]: {
            [label: string]: Record<string, number | null | string>;
        };
    };
    periods: number[];
    statement_type: string;
}

export interface DetectedStatement {
    statement_type: 'income_statement' | 'balance_sheet' | 'cash_flow';
    score: number;
    confidence: number;
}

export interface DetectStatementsResponse {
    document_id: string;
    detected_statements: DetectedStatement[];
    primary_statement: string;
    is_multi_statement: boolean;
}

// Export APIs
export const getExportOptions = async (): Promise<ExportOptionsResponse> => {
    const response = await api.get('/export/options');
    return response.data;
};

export const exportToExcel = async (request: ExportRequest): Promise<ExportResponse> => {
    const response = await api.post('/export/excel', request);
    return response.data;
};

export const getExportPreview = async (request: ExportRequest): Promise<ExportPreviewResponse> => {
    const response = await api.post('/export/preview', request);
    return response.data;
};

export const downloadExport = (exportId: string): string => {
    return `${API_BASE_URL}/export/download/${exportId}`;
};

export const detectStatements = async (documentId: string): Promise<DetectStatementsResponse> => {
    const response = await api.get(`/export/detect/${documentId}`);
    return response.data;
};

export default api;

