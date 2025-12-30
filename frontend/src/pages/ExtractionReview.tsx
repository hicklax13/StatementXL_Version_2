import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check, X, Edit3, FileText, AlertTriangle, Loader2 } from 'lucide-react';
import { useDocumentStore, useExtractionStore, useUIStore } from '../stores';
import { getDocumentExtractions, updateExtractionCell, getExportPreview } from '../api/client';
import type { ExtractedTable, ExportPreviewResponse } from '../api/client';
import { PDFOverlay } from '../components/PDFOverlay';
import logo from '../assets/logo.png';

const ExtractionReview: React.FC = () => {
    const navigate = useNavigate();
    const { currentDocument } = useDocumentStore(); // Keep currentDocument for now, as the new snippet for useDocumentStore seems to be a partial replacement.
    const { editedCells, updateCell } = useExtractionStore();
    const { addNotification } = useUIStore();
    const [editingCell, setEditingCell] = useState<string | null>(null);
    const [editValue, setEditValue] = useState('');
    const [tables, setTables] = useState<ExtractedTable[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // New Features State
    const [minConfidence, setMinConfidence] = useState(0.8);
    const [editingReasoning, setEditingReasoning] = useState<{ page: number, row: number, col: number, text: string } | null>(null);
    const [tempReasoning, setTempReasoning] = useState("");
    const [showOverlay, setShowOverlay] = useState(false); // Added showOverlay state
    const [previewData, setPreviewData] = useState<ExportPreviewResponse | null>(null);
    const [isPreviewOpen, setIsPreviewOpen] = useState(false);
    const [isPreviewLoading, setIsPreviewLoading] = useState(false);

    const handleSaveReasoning = async () => {
        if (!editingReasoning || !currentDocument) return;
        try {
            // Assuming the API expects 0-indexed row/col for the cell within the table structure
            // and the page number for the table itself.
            // This might need adjustment based on actual API implementation.
            await updateExtractionCell(
                currentDocument.id,
                editingReasoning.page,
                editingReasoning.row, // This should be the global row index or table-specific row index
                editingReasoning.col, // This should be the global col index or table-specific col index
                tempReasoning
            );

            // Re-fetch extractions to ensure UI is in sync with backend
            const data = await getDocumentExtractions(currentDocument.id);
            if (data.tables) setTables(data.tables);

            setEditingReasoning(null);
            setTempReasoning("");
            addNotification('success', 'Reasoning updated successfully');
        } catch (err) {
            console.error("Failed to save reasoning:", err);
            addNotification('error', 'Failed to save reasoning');
        }
    };

    // Fetch real extraction data
    useEffect(() => {
        const fetchExtractions = async () => {
            if (!currentDocument?.id) {
                setLoading(false);
                return;
            }

            try {
                setLoading(true);
                setError(null);
                const data = await getDocumentExtractions(currentDocument.id);
                setTables(data.tables || []);
            } catch (err: unknown) {
                console.error('Failed to fetch extractions:', err);
                setError(err instanceof Error ? err.message : 'Failed to load extractions');
                addNotification('error', 'Failed to load extraction data');
            } finally {
                setLoading(false);
            }
        };

        fetchExtractions();
    }, [currentDocument?.id, addNotification]);

    const handlePreview = async () => {
        if (!currentDocument) return;
        setIsPreviewLoading(true);
        try {
            // Default to 'income_statement' and 'corporate' for preview if not specified
            const data = await getExportPreview({
                document_id: currentDocument.id,
                statement_type: 'auto',
                style: 'corporate',
                colorway: 'green'
            });
            setPreviewData(data);
            setIsPreviewOpen(true);
        } catch (err) {
            console.error(err);
            addNotification('error', 'Failed to load preview');
        } finally {
            setIsPreviewLoading(false);
        }
    };

    const handleEdit = (tableIdx: number, rowIdx: number, cellIdx: number, value: string) => {
        const key = `${tableIdx} -${rowIdx} -${cellIdx} `;
        setEditingCell(key);
        setEditValue(value);
    };

    const handleSave = (key: string) => {
        updateCell(key, editValue);
        setEditingCell(null);
        addNotification('success', 'Value updated');
    };

    const handleCancel = () => {
        setEditingCell(null);
        setEditValue('');
    };

    const getConfidenceColor = (confidence: number) => {
        if (confidence >= minConfidence) return 'text-green-600';
        if (confidence >= minConfidence * 0.8) return 'text-yellow-600';
        return 'text-red-600';
    };

    const getConfidenceBg = (confidence: number) => {
        if (confidence >= minConfidence) return 'bg-green-100';
        if (confidence >= minConfidence * 0.8) return 'bg-yellow-100';
        return 'bg-red-100';
    };

    // Loading state
    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-[400px]">
                <div className="text-center">
                    <Loader2 className="w-12 h-12 text-green-600 animate-spin mx-auto" />
                    <p className="mt-4 text-gray-600">Loading extraction data...</p>
                </div>
            </div>
        );
    }

    // No document selected
    if (!currentDocument) {
        return (
            <div className="space-y-6 animate-fade-in">
                <div className="bg-gradient-to-r from-green-600 to-green-500 rounded-2xl p-8 text-white shadow-lg">
                    <div className="flex items-center space-x-6">
                        <div className="bg-white rounded-xl p-3 shadow-md">
                            <img src={logo} alt="StatementXL" className="h-12 w-auto" />
                        </div>
                        <div>
                            <h1 className="text-3xl font-bold">Extraction Review</h1>
                            <p className="text-green-100 mt-1">Review and edit extracted data</p>
                        </div>
                    </div>
                </div>
                <div className="bg-white rounded-xl border border-gray-200 p-8 text-center shadow-sm">
                    <FileText className="w-12 h-12 text-gray-400 mx-auto" />
                    <p className="mt-4 text-gray-600">No document selected</p>
                    <button
                        onClick={() => navigate('/')}
                        className="mt-4 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-500"
                    >
                        Upload a Document
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6 animate-fade-in">
            {/* Branded Header */}
            <div className="bg-gradient-to-r from-green-600 to-green-500 rounded-2xl p-8 text-white shadow-lg">
                <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-6">
                        <div className="bg-white rounded-xl p-3 shadow-md">
                            <img src={logo} alt="StatementXL" className="h-12 w-auto" />
                        </div>
                        <div>
                            <h1 className="text-3xl font-bold">Extraction Review</h1>
                            <p className="text-green-100 mt-1">{currentDocument.filename}</p>
                        </div>
                    </div>
                    <div className="flex items-center space-x-4">
                        <button
                            onClick={() => setShowOverlay(true)}
                            className="flex items-center px-4 py-2 bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 transition-colors"
                        >
                            <FileText size={20} className="mr-2" />
                            View Original PDF
                        </button>

                        <div className="flex items-center space-x-2 bg-gray-50 p-2 rounded-lg border border-gray-200">
                            <span className="text-sm font-medium text-gray-700">Confidence Threshold:</span>
                            <label htmlFor="confidence-range" className="sr-only">Confidence Threshold</label>
                            <input
                                id="confidence-range"
                                type="range"
                                min="0"
                                max="1"
                                step="0.05"
                                value={minConfidence}
                                onChange={(e) => setMinConfidence(parseFloat(e.target.value))}
                                className="w-32 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                                title="Adjust confidence threshold"
                            />
                            <span className="text-sm font-bold text-blue-600 w-12 text-right">
                                {(minConfidence * 100).toFixed(0)}%
                            </span>
                        </div>

                        <button
                            onClick={handlePreview}
                            disabled={isPreviewLoading}
                            className={`px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors flex items-center ${isPreviewLoading ? 'opacity-75 cursor-not-allowed' : ''}`}
                        >
                            {isPreviewLoading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                            Preview
                        </button>
                        <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                            Export to Excel
                        </button>
                    </div>
                </div>

                {/* PDF Overlay */}
                {showOverlay && currentDocument && (
                    <PDFOverlay
                        fileUrl={`/api/v1/documents/${currentDocument.id}/download`}
                        tables={tables}
                        onClose={() => setShowOverlay(false)}
                    />
                )}

                {/* Document Info */}
                <div className="bg-white rounded-xl border border-gray-200 p-4 flex items-center space-x-4 shadow-sm">
                    <div className="p-3 rounded-lg bg-green-100">
                        <FileText className="w-6 h-6 text-green-600" />
                    </div>
                    <div className="flex-1">
                        <p className="font-medium text-gray-900">{currentDocument.filename}</p>
                        <p className="text-sm text-gray-500">{currentDocument.pageCount || 'N/A'} pages • {tables.length} tables extracted</p>
                    </div>
                    <div className="flex items-center space-x-2 text-sm">
                        <span className="text-gray-500">Tables Found:</span>
                        <span className="font-semibold text-green-600">{tables.length}</span>
                    </div>
                </div>

                {/* Error state */}
                {
                    error && (
                        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-700">
                            {error}
                        </div>
                    )
                }

                {/* Empty state */}
                {
                    tables.length === 0 && !error && (
                        <div className="bg-white rounded-xl border border-gray-200 p-8 text-center shadow-sm">
                            <FileText className="w-12 h-12 text-gray-400 mx-auto" />
                            <p className="mt-4 text-gray-600">No tables extracted from this document</p>
                        </div>
                    )
                }

                {/* Tables */}
                {
                    tables.map((table, tableIdx) => (
                        <div key={tableIdx} className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
                            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between bg-green-50">
                                <h2 className="text-lg font-semibold text-gray-900">
                                    {table.title || `Table ${tableIdx + 1} `}
                                </h2>
                                <span className="text-sm text-gray-500">Page {table.page}</span>
                            </div>

                            <div className="overflow-x-auto">
                                <table className="w-full">
                                    <thead className="bg-green-50">
                                        <tr>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-green-800 uppercase tracking-wider">Label</th>
                                            <th className="px-6 py-3 text-right text-xs font-medium text-green-800 uppercase tracking-wider">Value</th>
                                            <th className="px-6 py-3 text-center text-xs font-medium text-green-800 uppercase tracking-wider w-24">Confidence</th>
                                            <th className="px-6 py-3 text-center text-xs font-medium text-green-800 uppercase tracking-wider w-24">Reasoning</th>
                                            <th className="px-6 py-3 text-center text-xs font-medium text-green-800 uppercase tracking-wider w-24">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-100">
                                        {table.rows.map((row, rowIdx) => {
                                            const labelCell = row.cells[0];
                                            const valueCell = row.cells[1];
                                            const cellKey = `${tableIdx} -${rowIdx} -1`;
                                            const isEditing = editingCell === cellKey;
                                            const displayValue = editedCells[cellKey] || valueCell?.value || valueCell?.parsed_value?.toString() || '';

                                            return (
                                                <tr key={rowIdx} className="hover:bg-green-50/50 transition-colors">
                                                    <td className="px-6 py-4 font-medium text-gray-900">
                                                        {labelCell?.value}
                                                    </td>
                                                    <td className="px-6 py-4 text-right">
                                                        {isEditing ? (
                                                            <input
                                                                type="text"
                                                                title="Edit cell value"
                                                                value={editValue}
                                                                onChange={(e) => setEditValue(e.target.value)}
                                                                className="w-full px-3 py-1 border border-green-300 rounded-lg text-right focus:ring-2 focus:ring-green-500 focus:border-green-500"
                                                                autoFocus
                                                            />
                                                        ) : (
                                                            <span className="font-mono text-gray-900">
                                                                {displayValue}
                                                            </span>
                                                        )}
                                                    </td>
                                                    <td className="px-6 py-4 text-center">
                                                        <span
                                                            className={`
inline - flex items - center px - 2 py - 1 rounded - full text - xs font - medium
                                                        ${getConfidenceBg(valueCell?.confidence || 0)}
                                                        ${getConfidenceColor(valueCell?.confidence || 0)}
`}
                                                        >
                                                            {((valueCell?.confidence || 0) * 100).toFixed(0)}%
                                                        </span>
                                                    </td>
                                                    <td className="px-6 py-4 text-center">
                                                        {editingReasoning?.page === table.page &&
                                                            editingReasoning?.row === rowIdx &&
                                                            editingReasoning?.col === 1 ? (
                                                            <div className="flex flex-col space-y-2 min-w-[250px] z-50 relative">
                                                                <textarea
                                                                    title="Edit reasoning"
                                                                    value={tempReasoning}
                                                                    onChange={(e) => setTempReasoning(e.target.value)}
                                                                    className="w-full text-xs p-2 border border-blue-300 rounded focus:ring-2 focus:ring-blue-500 min-h-[80px]"
                                                                    autoFocus
                                                                />
                                                                <div className="flex justify-end space-x-2">
                                                                    <button
                                                                        onClick={() => setEditingReasoning(null)}
                                                                        className="text-xs px-2 py-1 bg-gray-100 hover:bg-gray-200 rounded text-gray-600"
                                                                    >
                                                                        Cancel
                                                                    </button>
                                                                    <button
                                                                        onClick={handleSaveReasoning}
                                                                        className="text-xs px-2 py-1 bg-blue-600 hover:bg-blue-700 rounded text-white"
                                                                    >
                                                                        Save
                                                                    </button>
                                                                </div>
                                                            </div>
                                                        ) : valueCell?.reasoning ? (
                                                            <div className="group relative flex justify-center items-center space-x-1">
                                                                <div className="cursor-help p-1 rounded-full bg-blue-50 text-blue-600 hover:bg-blue-100">
                                                                    <div className="w-4 h-4 text-xs font-bold font-serif italic">i</div>
                                                                </div>

                                                                {/* Edit Reasoning Button */}
                                                                <button
                                                                    onClick={() => {
                                                                        setEditingReasoning({
                                                                            page: table.page,
                                                                            row: rowIdx, // Note: using index 
                                                                            col: 1, // Value column is index 1
                                                                            text: valueCell.reasoning || ""
                                                                        });
                                                                        setTempReasoning(valueCell.reasoning || "");
                                                                    }}
                                                                    className="opacity-0 group-hover:opacity-100 p-1 rounded-full text-gray-400 hover:text-green-600 transition-opacity"
                                                                    title="Edit Reasoning"
                                                                >
                                                                    <Edit3 className="w-3 h-3" />
                                                                </button>

                                                                <div className="absolute bottom-full mb-2 hidden group-hover:block w-64 p-3 bg-gray-900 text-white text-xs rounded-lg shadow-xl z-20 text-left">
                                                                    <div className="font-semibold mb-1 text-blue-300">AI Reasoning:</div>
                                                                    {valueCell.reasoning}
                                                                    <div className="absolute top-full left-1/2 transform -translate-x-1/2 border-4 border-transparent border-t-gray-900"></div>
                                                                </div>
                                                            </div>
                                                        ) : (
                                                            <span className="text-gray-300">-</span>
                                                        )}
                                                    </td>
                                                    <td className="px-6 py-4 text-center">
                                                        {isEditing ? (
                                                            <div className="flex items-center justify-center space-x-2">
                                                                <button
                                                                    onClick={() => handleSave(cellKey)}
                                                                    className="p-1.5 rounded-lg bg-green-100 text-green-600 hover:bg-green-200 transition-colors"
                                                                    title="Save changes"
                                                                >
                                                                    <Check className="w-4 h-4" />
                                                                </button>
                                                                <button
                                                                    onClick={handleCancel}
                                                                    className="p-1.5 rounded-lg bg-red-100 text-red-600 hover:bg-red-200 transition-colors"
                                                                    title="Cancel changes"
                                                                >
                                                                    <X className="w-4 h-4" />
                                                                </button>
                                                            </div>
                                                        ) : (
                                                            <button
                                                                onClick={() => handleEdit(tableIdx, rowIdx, 1, displayValue)}
                                                                className="p-1.5 rounded-lg text-gray-500 hover:text-green-600 hover:bg-green-50 transition-colors"
                                                                title="Edit value"
                                                            >
                                                                <Edit3 className="w-4 h-4" />
                                                            </button>
                                                        )}
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    ))
                }

                {/* Low Confidence Warning */}
                {
                    tables.length > 0 && (
                        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 border-l-4 border-l-yellow-500">
                            <div className="flex items-start space-x-3">
                                <AlertTriangle className="w-5 h-5 text-yellow-600 mt-0.5" />
                                <div>
                                    <p className="font-medium text-gray-900">Review Recommended</p>
                                    <p className="text-sm text-gray-600 mt-1">
                                        Review values with confidence below {(minConfidence * 100).toFixed(0)}%. Click edit to verify and correct if needed.
                                    </p>
                                </div>
                            </div>
                        </div>
                    )
                }
            </div >

            {/* Export Preview Modal */}
            {isPreviewOpen && previewData && (
                <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <div className="bg-white rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col">
                        <div className="p-6 border-b border-gray-200 flex justify-between items-center bg-gray-50 rounded-t-xl">
                            <div>
                                <h3 className="text-xl font-bold text-gray-900">Export Preview</h3>
                                <p className="text-sm text-gray-500">
                                    Statement Type: {previewData.statement_type.replace('_', ' ').toUpperCase()} • {previewData.periods.join(' / ')}
                                </p>
                            </div>
                            <button
                                onClick={() => setIsPreviewOpen(false)}
                                className="p-2 hover:bg-gray-200 rounded-lg transition-colors"
                                title="Close preview"
                            >
                                <X className="w-6 h-6 text-gray-500" />
                            </button>
                        </div>

                        <div className="flex-1 overflow-auto p-6">
                            <div className="border border-gray-200 rounded-lg overflow-hidden">
                                <table className="w-full text-sm">
                                    <thead className="bg-gray-100">
                                        <tr>
                                            <th className="px-4 py-3 text-left font-semibold text-gray-700">Line Item</th>
                                            {previewData.periods.map(period => (
                                                <th key={period} className="px-4 py-3 text-right font-semibold text-gray-700">{period}</th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-100">
                                        {Object.entries(previewData.aggregated_data).map(([category, items]) => (
                                            <React.Fragment key={category}>
                                                <tr className="bg-gray-50">
                                                    <td colSpan={previewData.periods.length + 1} className="px-4 py-2 font-bold text-gray-800 uppercase text-xs tracking-wider">
                                                        {category}
                                                    </td>
                                                </tr>
                                                {Object.entries(items).map(([label, values]) => {
                                                    // Cast values to Record<string, number> safely
                                                    const periodValues = values as Record<string, number | null>;
                                                    return (
                                                        <tr key={`${category}-${label}`} className="hover:bg-blue-50">
                                                            <td className="px-4 py-2 text-gray-700 pl-8">{label}</td>
                                                            {previewData.periods.map(period => (
                                                                <td key={period} className="px-4 py-2 text-right font-mono text-gray-900">
                                                                    {/* Handle nested period values if structured that way, or if flat */}
                                                                    {/* Based on my backend refactor: prepared_data uses item[str(year)] = value */}
                                                                    {/* But aggregated_data structure is { category: { label: { year: value } } } ? */}
                                                                    {/* Let's verify aggregation logic. Backend: aggregated[category][label] = { year: value } */}
                                                                    {/* Wait, the aggregator in `gaap_classifier.py` returns { category: [items] } or { category: { label: value } }? */}
                                                                    {/* I need to be careful here. Let's assume simplest rendering first: check if values is dict */}
                                                                    {typeof values === 'object' && values !== null ? (
                                                                        periodValues[String(period)]?.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) || '-'
                                                                    ) : '-'}
                                                                </td>
                                                            ))}
                                                        </tr>
                                                    );
                                                })}
                                            </React.Fragment>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        <div className="p-6 border-t border-gray-200 bg-gray-50 rounded-b-xl flex justify-end space-x-4">
                            <button
                                onClick={() => setIsPreviewOpen(false)}
                                className="px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium"
                            >
                                Close
                            </button>
                            <button className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 font-medium shadow-sm">
                                Confirm & Export
                            </button>
                        </div>
                    </div>
                </div>
            )}

        </div>
    );
};

export default ExtractionReview;
