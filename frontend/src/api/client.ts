import axios from 'axios';

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
    extracted_items: any[];
    template_targets: any[];
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

export default api;
