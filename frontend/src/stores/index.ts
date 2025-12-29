import { create } from 'zustand';

// Types
export interface Document {
    id: string;
    filename: string;
    status: 'pending' | 'processing' | 'completed' | 'failed' | 'reasoning';
    pageCount?: number;
    createdAt: string;
}

export interface ExtractedTable {
    page: number;
    rows: Array<{
        cells: Array<{
            value: string;
            confidence: number;
            reasoning?: string;
        }>;
    }>;
}

export interface Extraction {
    documentId: string;
    tables: ExtractedTable[];
    confidence: number;
}

export interface Template {
    id: string;
    filename: string;
    sheetCount: number;
    status: 'pending' | 'processing' | 'completed' | 'failed';
    createdAt: string;
}

export interface MappingAssignment {
    sourceLabel: string;
    sourceValue: number | null;
    targetAddress: string;
    confidence: number;
    matchType: string;
    isAutoMapped: boolean;
}

export interface Conflict {
    id: string;
    conflictType: string;
    severity: 'critical' | 'high' | 'medium' | 'low';
    description: string;
    sourceLabel?: string;
    targetAddress?: string;
    suggestions: string[];
    isResolved: boolean;
}

export interface MappingGraph {
    id: string;
    status: 'pending' | 'processing' | 'completed' | 'needs_review' | 'failed';
    totalItems: number;
    mappedCount: number;
    autoMappedCount: number;
    conflictCount: number;
    averageConfidence: number;
    assignments: MappingAssignment[];
    conflicts: Conflict[];
}

// Document Store
interface DocumentState {
    documents: Document[];
    currentDocument: Document | null;
    isUploading: boolean;
    uploadProgress: number;
    setDocuments: (docs: Document[]) => void;
    addDocument: (doc: Document) => void;
    setCurrentDocument: (doc: Document | null) => void;
    setUploading: (uploading: boolean) => void;
    setUploadProgress: (progress: number) => void;
}

export const useDocumentStore = create<DocumentState>((set) => ({
    documents: [],
    currentDocument: null,
    isUploading: false,
    uploadProgress: 0,
    setDocuments: (documents) => set({ documents }),
    addDocument: (doc) => set((state) => ({ documents: [...state.documents, doc] })),
    setCurrentDocument: (currentDocument) => set({ currentDocument }),
    setUploading: (isUploading) => set({ isUploading }),
    setUploadProgress: (uploadProgress) => set({ uploadProgress }),
}));

// Extraction Store
interface ExtractionState {
    extraction: Extraction | null;
    editedCells: Record<string, string>;
    setExtraction: (extraction: Extraction | null) => void;
    updateCell: (key: string, value: string) => void;
    clearEdits: () => void;
}

export const useExtractionStore = create<ExtractionState>((set) => ({
    extraction: null,
    editedCells: {},
    setExtraction: (extraction) => set({ extraction }),
    updateCell: (key, value) => set((state) => ({
        editedCells: { ...state.editedCells, [key]: value },
    })),
    clearEdits: () => set({ editedCells: {} }),
}));

// Template Store
interface TemplateState {
    templates: Template[];
    currentTemplate: Template | null;
    setTemplates: (templates: Template[]) => void;
    addTemplate: (template: Template) => void;
    setCurrentTemplate: (template: Template | null) => void;
}

export const useTemplateStore = create<TemplateState>((set) => ({
    templates: [],
    currentTemplate: null,
    setTemplates: (templates) => set({ templates }),
    addTemplate: (template) => set((state) => ({ templates: [...state.templates, template] })),
    setCurrentTemplate: (currentTemplate) => set({ currentTemplate }),
}));

// Mapping Store
interface MappingState {
    mapping: MappingGraph | null;
    selectedConflict: Conflict | null;
    setMapping: (mapping: MappingGraph | null) => void;
    setSelectedConflict: (conflict: Conflict | null) => void;
    resolveConflict: (conflictId: string) => void;
}

export const useMappingStore = create<MappingState>((set) => ({
    mapping: null,
    selectedConflict: null,
    setMapping: (mapping) => set({ mapping }),
    setSelectedConflict: (selectedConflict) => set({ selectedConflict }),
    resolveConflict: (conflictId) => set((state) => ({
        mapping: state.mapping ? {
            ...state.mapping,
            conflicts: state.mapping.conflicts.map((c) =>
                c.id === conflictId ? { ...c, isResolved: true } : c
            ),
            conflictCount: state.mapping.conflictCount - 1,
        } : null,
    })),
}));

// UI Store
interface UIState {
    sidebarOpen: boolean;
    activeTab: string;
    notifications: Array<{ id: string; type: 'success' | 'error' | 'info'; message: string }>;
    toggleSidebar: () => void;
    setActiveTab: (tab: string) => void;
    addNotification: (type: 'success' | 'error' | 'info', message: string) => void;
    removeNotification: (id: string) => void;
}

export const useUIStore = create<UIState>((set) => ({
    sidebarOpen: true,
    activeTab: 'upload',
    notifications: [],
    toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
    setActiveTab: (activeTab) => set({ activeTab }),
    addNotification: (type, message) => set((state) => ({
        notifications: [...state.notifications, { id: Date.now().toString(), type, message }],
    })),
    removeNotification: (id) => set((state) => ({
        notifications: state.notifications.filter((n) => n.id !== id),
    })),
}));
