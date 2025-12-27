import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    CheckCircle,
    AlertTriangle,
    XCircle,
    ChevronDown,
    ChevronUp,
    Download,
    ThumbsUp,
    Edit3,
    Loader2,
} from 'lucide-react';
import { useMappingStore, useUIStore } from '../stores';
import { getMapping, getMappingConflicts, resolveConflict as resolveConflictApi } from '../api/client';
import logo from '../assets/logo.png';

interface ConflictItemProps {
    conflict: {
        id: string;
        conflict_type: string;
        severity: 'critical' | 'high' | 'medium' | 'low';
        description: string;
        source_label?: string;
        target_address?: string;
        suggestions: string[];
        is_resolved: boolean;
    };
    mappingId: string;
    onResolve: (id: string, resolution: string) => void;
}

const ConflictItem: React.FC<ConflictItemProps> = ({ conflict, onResolve }) => {
    const [expanded, setExpanded] = useState(false);
    const [selectedSuggestion, setSelectedSuggestion] = useState<string | null>(null);
    const [resolving, setResolving] = useState(false);

    const getSeverityColor = (severity: string) => {
        switch (severity) {
            case 'critical': return 'border-l-red-500 bg-red-50';
            case 'high': return 'border-l-orange-500 bg-orange-50';
            case 'medium': return 'border-l-yellow-500 bg-yellow-50';
            default: return 'border-l-blue-500 bg-blue-50';
        }
    };

    const getSeverityIcon = (severity: string) => {
        switch (severity) {
            case 'critical': return <XCircle className="w-5 h-5 text-red-600" />;
            case 'high': return <AlertTriangle className="w-5 h-5 text-orange-600" />;
            case 'medium': return <AlertTriangle className="w-5 h-5 text-yellow-600" />;
            default: return <AlertTriangle className="w-5 h-5 text-blue-600" />;
        }
    };

    const handleResolve = async () => {
        if (!selectedSuggestion) return;
        setResolving(true);
        try {
            await onResolve(conflict.id, selectedSuggestion);
        } finally {
            setResolving(false);
        }
    };

    if (conflict.is_resolved) {
        return (
            <div className="p-4 rounded-lg bg-gray-100 border border-gray-200 opacity-60">
                <div className="flex items-center space-x-3">
                    <CheckCircle className="w-5 h-5 text-green-600" />
                    <span className="text-gray-500 line-through">{conflict.description}</span>
                </div>
            </div>
        );
    }

    return (
        <div className={`rounded-lg border-l-4 ${getSeverityColor(conflict.severity)}`}>
            <div
                className="p-4 flex items-center justify-between cursor-pointer"
                onClick={() => setExpanded(!expanded)}
            >
                <div className="flex items-center space-x-3">
                    {getSeverityIcon(conflict.severity)}
                    <div>
                        <p className="font-medium text-gray-900">{conflict.description}</p>
                        <p className="text-sm text-gray-500">
                            {conflict.source_label && `Source: ${conflict.source_label}`}
                            {conflict.target_address && ` → Target: ${conflict.target_address}`}
                        </p>
                    </div>
                </div>
                {expanded ? (
                    <ChevronUp className="w-5 h-5 text-gray-400" />
                ) : (
                    <ChevronDown className="w-5 h-5 text-gray-400" />
                )}
            </div>

            {expanded && (
                <div className="px-4 pb-4 space-y-4 animate-slide-down">
                    <div>
                        <p className="text-sm font-medium text-gray-700 mb-2">Suggestions:</p>
                        <div className="space-y-2">
                            {conflict.suggestions.map((suggestion, idx) => (
                                <button
                                    key={idx}
                                    onClick={() => setSelectedSuggestion(suggestion)}
                                    className={`
                                        w-full p-3 rounded-lg text-left text-sm transition-all
                                        ${selectedSuggestion === suggestion
                                            ? 'bg-green-100 border border-green-500 text-green-800'
                                            : 'bg-gray-100 border border-gray-200 text-gray-700 hover:border-gray-300'
                                        }
                                    `}
                                >
                                    {suggestion}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div className="flex items-center space-x-3">
                        <button
                            onClick={handleResolve}
                            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-500 transition-colors flex items-center space-x-2 disabled:opacity-50"
                            disabled={!selectedSuggestion || resolving}
                        >
                            {resolving ? <Loader2 className="w-4 h-4 animate-spin" /> : <ThumbsUp className="w-4 h-4" />}
                            <span>Accept</span>
                        </button>
                        <button className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors flex items-center space-x-2">
                            <Edit3 className="w-4 h-4" />
                            <span>Manual Edit</span>
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};

const MappingReview: React.FC = () => {
    const navigate = useNavigate();
    const { mapping, resolveConflict } = useMappingStore();
    const { addNotification } = useUIStore();
    const [mappingData, setMappingData] = useState<Record<string, unknown> | null>(null);
    const [conflicts, setConflicts] = useState<ConflictItemProps['conflict'][]>([]);
    const [loading, setLoading] = useState(true);

    // Fetch mapping data if available
    useEffect(() => {
        const fetchMapping = async () => {
            if (mapping?.id) {
                try {
                    setLoading(true);
                    const data = await getMapping(mapping.id);
                    setMappingData(data);
                    const conflictData = await getMappingConflicts(mapping.id);
                    setConflicts(conflictData.conflicts || []);
                } catch (err) {
                    console.error('Failed to fetch mapping:', err);
                } finally {
                    setLoading(false);
                }
            } else {
                // Use demo data if no mapping exists
                setMappingData({
                    mapping_id: 'demo',
                    status: 'needs_review',
                    total_items: 25,
                    mapped_count: 22,
                    auto_mapped_count: 18,
                    conflict_count: 3,
                    average_confidence: 0.87,
                });
                setConflicts([
                    {
                        id: '1',
                        conflict_type: 'low_confidence',
                        severity: 'high',
                        description: 'Low confidence mapping for "Operating Expenses"',
                        source_label: 'Operating Expenses',
                        target_address: 'B15',
                        suggestions: ['Map to Operating Expenses cell', 'Map to SG&A cell', 'Skip this item'],
                        is_resolved: false,
                    },
                    {
                        id: '2',
                        conflict_type: 'missing_required',
                        severity: 'critical',
                        description: 'Template cell "Interest Expense" has no mapping',
                        source_label: undefined,
                        target_address: 'B20',
                        suggestions: ['Search extracted data', 'Enter value manually', 'Mark as N/A'],
                        is_resolved: false,
                    },
                ]);
                setLoading(false);
            }
        };

        fetchMapping();
    }, [mapping?.id]);

    const handleResolve = async (conflictId: string, resolution: string) => {
        try {
            if (mapping?.id) {
                await resolveConflictApi(mapping.id, conflictId, resolution);
            }
            resolveConflict(conflictId);
            setConflicts(prev => prev.map(c =>
                c.id === conflictId ? { ...c, is_resolved: true } : c
            ));
            addNotification('success', 'Conflict resolved');
        } catch {
            addNotification('error', 'Failed to resolve conflict');
        }
    };

    const unresolvedCount = conflicts.filter((c) => !c.is_resolved).length;
    const data = mappingData || { total_items: 0, mapped_count: 0, auto_mapped_count: 0, average_confidence: 0 };

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-[400px]">
                <div className="text-center">
                    <Loader2 className="w-12 h-12 text-green-600 animate-spin mx-auto" />
                    <p className="mt-4 text-gray-600">Loading mapping data...</p>
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
                            <h1 className="text-3xl font-bold">Mapping Review</h1>
                            <p className="text-green-100 mt-1">Review and resolve mapping conflicts</p>
                        </div>
                    </div>
                    <div className="flex items-center space-x-3">
                        <button
                            onClick={() => navigate('/audit')}
                            className="px-4 py-2 bg-white/20 text-white rounded-lg hover:bg-white/30 transition-colors"
                        >
                            View Audit Trail
                        </button>
                        <button
                            className="px-4 py-2 bg-white text-green-600 rounded-lg hover:bg-green-50 transition-colors flex items-center space-x-2 font-medium shadow-sm disabled:opacity-50"
                            disabled={unresolvedCount > 0}
                        >
                            <Download className="w-4 h-4" />
                            <span>Export Excel</span>
                        </button>
                    </div>
                </div>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
                    <p className="text-sm text-gray-500">Total Items</p>
                    <p className="text-2xl font-bold mt-1 text-gray-900">{data.total_items}</p>
                </div>
                <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
                    <p className="text-sm text-gray-500">Auto Mapped</p>
                    <p className="text-2xl font-bold mt-1 text-green-600">{data.auto_mapped_count}</p>
                </div>
                <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
                    <p className="text-sm text-gray-500">Avg Confidence</p>
                    <p className="text-2xl font-bold mt-1 text-green-600">{(data.average_confidence * 100).toFixed(0)}%</p>
                </div>
                <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
                    <p className="text-sm text-gray-500">Conflicts</p>
                    <p className={`text-2xl font-bold mt-1 ${unresolvedCount > 0 ? 'text-red-600' : 'text-green-600'}`}>
                        {unresolvedCount}
                    </p>
                </div>
            </div>

            {/* Progress Bar */}
            <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
                <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-gray-900">Mapping Progress</span>
                    <span className="text-sm text-gray-500">
                        {data.mapped_count} / {data.total_items} items
                    </span>
                </div>
                <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div
                        className="h-full bg-gradient-to-r from-green-600 to-green-400 transition-all duration-500"
                        style={{ width: `${data.total_items > 0 ? (data.mapped_count / data.total_items) * 100 : 0}%` }}
                    />
                </div>
            </div>

            {/* Conflicts */}
            <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
                <h2 className="text-lg font-semibold text-gray-900 mb-4">
                    Conflicts to Review ({unresolvedCount})
                </h2>
                <div className="space-y-4">
                    {conflicts.map((conflict) => (
                        <ConflictItem
                            key={conflict.id}
                            conflict={conflict}
                            mappingId={mapping?.id || ''}
                            onResolve={handleResolve}
                        />
                    ))}
                </div>
            </div>

            {/* Continue Button */}
            {unresolvedCount === 0 && (
                <div className="bg-green-50 border border-green-200 rounded-xl p-6 border-l-4 border-l-green-500">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-3">
                            <CheckCircle className="w-6 h-6 text-green-600" />
                            <div>
                                <p className="font-medium text-gray-900">All Conflicts Resolved!</p>
                                <p className="text-sm text-gray-600">Ready to export your populated template</p>
                            </div>
                        </div>
                        <button className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-500 transition-colors flex items-center space-x-2">
                            <Download className="w-4 h-4" />
                            <span>Export Excel</span>
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};

export default MappingReview;
