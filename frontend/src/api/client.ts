import axios from 'axios';

// Type definitions
interface ExtractedItem {
    label: string;
    value: string | number | null;
    confidence?: number;
    page?: number;
}

interface TemplateTarget {
    address: string;
    row?: number;
    column?: number;
    sheet?: string;
}

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Document APIs
export const uploadDocument = async (file: File): Promise<any> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post('/upload', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
    return response.data;
};

export const getDocument = async (documentId: string): Promise<any> => {
    const response = await api.get(`/documents/${documentId}`);
    return response.data;
};

// Classification APIs
export const classifyItem = async (text: string): Promise<any> => {
    const response = await api.post('/classify', { text });
    return response.data;
};

export const classifyBatch = async (texts: string[]): Promise<any> => {
    const response = await api.post('/classify/batch', { texts });
    return response.data;
};

// Template APIs
export const uploadTemplate = async (file: File): Promise<any> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post('/template/upload', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
    return response.data;
};

export const getTemplate = async (templateId: string): Promise<any> => {
    const response = await api.get(`/template/${templateId}`);
    return response.data;
};

export const getTemplateGraph = async (templateId: string, format: string = 'json'): Promise<any> => {
    const response = await api.get(`/template/${templateId}/graph?format=${format}`);
    return response.data;
};

// Mapping APIs
export const createMapping = async (data: {
    extracted_items: ExtractedItem[];
    template_targets: TemplateTarget[];
    period?: string;
}): Promise<any> => {
    const response = await api.post('/map', data);
    return response.data;
};

export const getMapping = async (mappingId: string): Promise<any> => {
    const response = await api.get(`/mapping/${mappingId}`);
    return response.data;
};

export const getMappingConflicts = async (mappingId: string): Promise<any> => {
    const response = await api.get(`/mapping/${mappingId}/conflicts`);
    return response.data;
};

export const resolveConflict = async (
    mappingId: string,
    conflictId: string,
    resolution: string
): Promise<any> => {
    const response = await api.put(`/mapping/${mappingId}/conflicts/${conflictId}/resolve`, {
        conflict_id: conflictId,
        resolution,
    });
    return response.data;
};

// Extraction APIs
export const getDocumentExtractions = async (documentId: string): Promise<any> => {
    const response = await api.get(`/documents/${documentId}/extractions`);
    return response.data;
};

// Audit APIs
export const getAuditLog = async (
    page: number = 1,
    pageSize: number = 20,
    resourceType?: string,
    action?: string
): Promise<any> => {
    const params = new URLSearchParams();
    params.append('page', page.toString());
    params.append('page_size', pageSize.toString());
    if (resourceType) params.append('resource_type', resourceType);
    if (action) params.append('action', action);

    const response = await api.get(`/audit?${params.toString()}`);
    return response.data;
};

// Authentication APIs
export const register = async (email: string, password: string, fullName?: string): Promise<any> => {
    const response = await api.post('/auth/register', { email, password, full_name: fullName });
    return response.data;
};

export const login = async (email: string, password: string): Promise<any> => {
    const response = await api.post('/auth/login', { email, password });
    return response.data;
};

export const refreshToken = async (refreshTokenStr: string): Promise<any> => {
    const response = await api.post('/auth/refresh', { refresh_token: refreshTokenStr });
    return response.data;
};

export const getCurrentUser = async (): Promise<any> => {
    const response = await api.get('/auth/me');
    return response.data;
};

export const logout = async (): Promise<any> => {
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
