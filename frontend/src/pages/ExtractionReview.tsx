import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check, X, Edit3, Save, FileText, ArrowRight, AlertTriangle } from 'lucide-react';
import { useDocumentStore, useExtractionStore, useUIStore } from '../stores';

interface CellData {
    value: string;
    confidence: number;
    isEditing?: boolean;
}

const ExtractionReview: React.FC = () => {
    const navigate = useNavigate();
    const { currentDocument } = useDocumentStore();
    const { extraction, editedCells, updateCell } = useExtractionStore();
    const { addNotification } = useUIStore();
    const [editingCell, setEditingCell] = useState<string | null>(null);
    const [editValue, setEditValue] = useState('');

    // Mock data for demonstration
    const mockTables = [
        {
            page: 1,
            title: 'Income Statement',
            rows: [
                { cells: [{ value: 'Revenue', confidence: 1.0 }, { value: '5,234,000', confidence: 0.95 }] },
                { cells: [{ value: 'Cost of Goods Sold', confidence: 0.98 }, { value: '2,456,000', confidence: 0.92 }] },
                { cells: [{ value: 'Gross Profit', confidence: 1.0 }, { value: '2,778,000', confidence: 0.88 }] },
                { cells: [{ value: 'Operating Expenses', confidence: 0.95 }, { value: '1,234,000', confidence: 0.90 }] },
                { cells: [{ value: 'Operating Income', confidence: 1.0 }, { value: '1,544,000', confidence: 0.85 }] },
                { cells: [{ value: 'Net Income', confidence: 1.0 }, { value: '1,156,000', confidence: 0.94 }] },
            ],
        },
    ];

    const tables = extraction?.tables || mockTables;

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
        if (confidence >= 0.9) return 'text-green-400';
        if (confidence >= 0.7) return 'text-yellow-400';
        return 'text-red-400';
    };

    const getConfidenceBg = (confidence: number) => {
        if (confidence >= 0.9) return 'bg-green-500/10';
        if (confidence >= 0.7) return 'bg-yellow-500/10';
        return 'bg-red-500/10';
    };

    return (
        <div className="space-y-6 animate-fade-in">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold text-dark-100">Extraction Review</h1>
                    <p className="text-dark-400 mt-1">
                        {currentDocument?.filename || 'Review and edit extracted data'}
                    </p>
                </div>
                <button
                    onClick={() => navigate('/template')}
                    className="btn btn-primary flex items-center space-x-2"
                >
                    <span>Continue to Template</span>
                    <ArrowRight className="w-4 h-4" />
                </button>
            </div>

            {/* Document Info */}
            <div className="card p-4 flex items-center space-x-4">
                <div className="p-3 rounded-lg bg-primary-500/10">
                    <FileText className="w-6 h-6 text-primary-400" />
                </div>
                <div className="flex-1">
                    <p className="font-medium text-dark-100">{currentDocument?.filename || 'Sample Document.pdf'}</p>
                    <p className="text-sm text-dark-400">{currentDocument?.pageCount || 3} pages extracted</p>
                </div>
                <div className="flex items-center space-x-2 text-sm">
                    <span className="text-dark-400">Overall Confidence:</span>
                    <span className="font-semibold text-green-400">94%</span>
                </div>
            </div>

            {/* Tables */}
            {tables.map((table, tableIdx) => (
                <div key={tableIdx} className="card overflow-hidden">
                    <div className="px-6 py-4 border-b border-dark-700 flex items-center justify-between">
                        <h2 className="text-lg font-semibold text-dark-100">
                            {table.title || `Table ${tableIdx + 1}`}
                        </h2>
                        <span className="text-sm text-dark-400">Page {table.page}</span>
                    </div>

                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead className="table-header">
                                <tr>
                                    <th className="px-6 py-3 text-left">Label</th>
                                    <th className="px-6 py-3 text-right">Value</th>
                                    <th className="px-6 py-3 text-center w-24">Confidence</th>
                                    <th className="px-6 py-3 text-center w-24">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {table.rows.map((row, rowIdx) => {
                                    const labelCell = row.cells[0];
                                    const valueCell = row.cells[1];
                                    const cellKey = `${tableIdx}-${rowIdx}-1`;
                                    const isEditing = editingCell === cellKey;
                                    const displayValue = editedCells[cellKey] || valueCell?.value || '';

                                    return (
                                        <tr key={rowIdx} className="table-row">
                                            <td className="px-6 py-4 font-medium text-dark-100">
                                                {labelCell?.value}
                                            </td>
                                            <td className="px-6 py-4 text-right">
                                                {isEditing ? (
                                                    <input
                                                        type="text"
                                                        value={editValue}
                                                        onChange={(e) => setEditValue(e.target.value)}
                                                        className="input text-right"
                                                        autoFocus
                                                    />
                                                ) : (
                                                    <span className="font-mono text-dark-100">
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
                                                            className="p-1.5 rounded-lg bg-green-500/10 text-green-400 hover:bg-green-500/20 transition-colors"
                                                        >
                                                            <Check className="w-4 h-4" />
                                                        </button>
                                                        <button
                                                            onClick={handleCancel}
                                                            className="p-1.5 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors"
                                                        >
                                                            <X className="w-4 h-4" />
                                                        </button>
                                                    </div>
                                                ) : (
                                                    <button
                                                        onClick={() => handleEdit(tableIdx, rowIdx, 1, displayValue)}
                                                        className="p-1.5 rounded-lg text-dark-400 hover:text-primary-400 hover:bg-primary-500/10 transition-colors"
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
            <div className="card p-4 border-l-4 border-yellow-500 bg-yellow-500/5">
                <div className="flex items-start space-x-3">
                    <AlertTriangle className="w-5 h-5 text-yellow-500 mt-0.5" />
                    <div>
                        <p className="font-medium text-dark-100">Review Recommended</p>
                        <p className="text-sm text-dark-400 mt-1">
                            3 values have confidence below 90%. Click edit to verify and correct if needed.
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ExtractionReview;
