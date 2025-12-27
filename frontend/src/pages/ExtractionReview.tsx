import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check, X, Edit3, FileText, ArrowRight, AlertTriangle, Loader2 } from 'lucide-react';
import { useDocumentStore, useExtractionStore, useUIStore } from '../stores';
import { getDocumentExtractions } from '../api/client';
import type { ExtractedTable } from '../api/client';
import logo from '../assets/logo.png';

const ExtractionReview: React.FC = () => {
    const navigate = useNavigate();
    const { currentDocument } = useDocumentStore();
    const { editedCells, updateCell } = useExtractionStore();
    const { addNotification } = useUIStore();
    const [editingCell, setEditingCell] = useState<string | null>(null);
    const [editValue, setEditValue] = useState('');
    const [tables, setTables] = useState<ExtractedTable[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

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

    const handleEdit = (tableIdx: number, rowIdx: number, cellIdx: number, value: string) => {
        const key = `${tableIdx}-${rowIdx}-${cellIdx}`;
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
        if (confidence >= 0.9) return 'text-green-600';
        if (confidence >= 0.7) return 'text-yellow-600';
        return 'text-red-600';
    };

    const getConfidenceBg = (confidence: number) => {
        if (confidence >= 0.9) return 'bg-green-100';
        if (confidence >= 0.7) return 'bg-yellow-100';
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
                    <button
                        onClick={() => navigate('/template')}
                        className="px-4 py-2 bg-white text-green-600 rounded-lg hover:bg-green-50 transition-colors flex items-center space-x-2 font-medium shadow-sm"
                    >
                        <span>Continue to Template</span>
                        <ArrowRight className="w-4 h-4" />
                    </button>
                </div>
            </div>

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
            {error && (
                <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-700">
                    {error}
                </div>
            )}

            {/* Empty state */}
            {tables.length === 0 && !error && (
                <div className="bg-white rounded-xl border border-gray-200 p-8 text-center shadow-sm">
                    <FileText className="w-12 h-12 text-gray-400 mx-auto" />
                    <p className="mt-4 text-gray-600">No tables extracted from this document</p>
                </div>
            )}

            {/* Tables */}
            {tables.map((table, tableIdx) => (
                <div key={tableIdx} className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
                    <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between bg-green-50">
                        <h2 className="text-lg font-semibold text-gray-900">
                            {table.title || `Table ${tableIdx + 1}`}
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
                                    <th className="px-6 py-3 text-center text-xs font-medium text-green-800 uppercase tracking-wider w-24">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100">
                                {table.rows.map((row, rowIdx) => {
                                    const labelCell = row.cells[0];
                                    const valueCell = row.cells[1];
                                    const cellKey = `${tableIdx}-${rowIdx}-1`;
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
                                                        inline-flex items-center px-2 py-1 rounded-full text-xs font-medium
                                                        ${getConfidenceBg(valueCell?.confidence || 0)}
                                                        ${getConfidenceColor(valueCell?.confidence || 0)}
                                                    `}
                                                >
                                                    {((valueCell?.confidence || 0) * 100).toFixed(0)}%
                                                </span>
                                            </td>
                                            <td className="px-6 py-4 text-center">
                                                {isEditing ? (
                                                    <div className="flex items-center justify-center space-x-2">
                                                        <button
                                                            onClick={() => handleSave(cellKey)}
                                                            className="p-1.5 rounded-lg bg-green-100 text-green-600 hover:bg-green-200 transition-colors"
                                                        >
                                                            <Check className="w-4 h-4" />
                                                        </button>
                                                        <button
                                                            onClick={handleCancel}
                                                            className="p-1.5 rounded-lg bg-red-100 text-red-600 hover:bg-red-200 transition-colors"
                                                        >
                                                            <X className="w-4 h-4" />
                                                        </button>
                                                    </div>
                                                ) : (
                                                    <button
                                                        onClick={() => handleEdit(tableIdx, rowIdx, 1, displayValue)}
                                                        className="p-1.5 rounded-lg text-gray-500 hover:text-green-600 hover:bg-green-50 transition-colors"
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
            ))}

            {/* Low Confidence Warning */}
            {tables.length > 0 && (
                <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 border-l-4 border-l-yellow-500">
                    <div className="flex items-start space-x-3">
                        <AlertTriangle className="w-5 h-5 text-yellow-600 mt-0.5" />
                        <div>
                            <p className="font-medium text-gray-900">Review Recommended</p>
                            <p className="text-sm text-gray-600 mt-1">
                                Review values with confidence below 90%. Click edit to verify and correct if needed.
                            </p>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default ExtractionReview;
