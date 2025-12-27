import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

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

export default api;
