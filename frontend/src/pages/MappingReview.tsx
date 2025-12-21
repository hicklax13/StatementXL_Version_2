import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    CheckCircle,
    AlertTriangle,
    XCircle,
    ChevronDown,
    ChevronUp,
    ArrowRight,
    Download,
    ThumbsUp,
    Edit3,
} from 'lucide-react';
import { useMappingStore, useUIStore } from '../stores';

interface ConflictItemProps {
    conflict: {
        id: string;
        conflictType: string;
        severity: 'critical' | 'high' | 'medium' | 'low';
        description: string;
        sourceLabel?: string;
        targetAddress?: string;
        suggestions: string[];
        isResolved: boolean;
    };
    onResolve: (id: string, resolution: string) => void;
}

const ConflictItem: React.FC<ConflictItemProps> = ({ conflict, onResolve }) => {
    const [expanded, setExpanded] = useState(false);
    const [selectedSuggestion, setSelectedSuggestion] = useState<string | null>(null);

    const getSeverityColor = (severity: string) => {
        switch (severity) {
            case 'critical': return 'border-red-500 bg-red-500/10';
            case 'high': return 'border-orange-500 bg-orange-500/10';
            case 'medium': return 'border-yellow-500 bg-yellow-500/10';
            default: return 'border-blue-500 bg-blue-500/10';
        }
    };

    const getSeverityIcon = (severity: string) => {
        switch (severity) {
            case 'critical': return <XCircle className="w-5 h-5 text-red-500" />;
            case 'high': return <AlertTriangle className="w-5 h-5 text-orange-500" />;
            case 'medium': return <AlertTriangle className="w-5 h-5 text-yellow-500" />;
            default: return <AlertTriangle className="w-5 h-5 text-blue-500" />;
        }
    };

    if (conflict.isResolved) {
        return (
            <div className="p-4 rounded-lg bg-dark-800/50 border border-dark-700 opacity-60">
                <div className="flex items-center space-x-3">
                    <CheckCircle className="w-5 h-5 text-green-500" />
                    <span className="text-dark-300 line-through">{conflict.description}</span>
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
                        <p className="font-medium text-dark-100">{conflict.description}</p>
                        <p className="text-sm text-dark-400">
                            {conflict.sourceLabel && `Source: ${conflict.sourceLabel}`}
                            {conflict.targetAddress && ` → Target: ${conflict.targetAddress}`}
                        </p>
                    </div>
                </div>
                {expanded ? (
                    <ChevronUp className="w-5 h-5 text-dark-400" />
                ) : (
                    <ChevronDown className="w-5 h-5 text-dark-400" />
                )}
            </div>

            {expanded && (
                <div className="px-4 pb-4 space-y-4 animate-slide-down">
                    <div>
                        <p className="text-sm font-medium text-dark-300 mb-2">Suggestions:</p>
                        <div className="space-y-2">
                            {conflict.suggestions.map((suggestion, idx) => (
                                <button
                                    key={idx}
                                    onClick={() => setSelectedSuggestion(suggestion)}
                                    className={`
                    w-full p-3 rounded-lg text-left text-sm transition-all
                    ${selectedSuggestion === suggestion
                                            ? 'bg-primary-500/20 border border-primary-500 text-primary-300'
                                            : 'bg-dark-700 border border-dark-600 text-dark-200 hover:border-dark-500'
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
                            onClick={() => onResolve(conflict.id, selectedSuggestion || 'Manual resolution')}
                            className="btn btn-primary flex items-center space-x-2"
                            disabled={!selectedSuggestion}
                        >
                            <ThumbsUp className="w-4 h-4" />
                            <span>Accept</span>
                        </button>
                        <button className="btn btn-secondary flex items-center space-x-2">
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

    // Mock data
    const mockMapping = {
        id: 'mock-mapping',
        status: 'needs_review' as const,
        totalItems: 25,
        mappedCount: 22,
        autoMappedCount: 18,
        conflictCount: 3,
        averageConfidence: 0.87,
        assignments: [],
        conflicts: [
            {
                id: '1',
                conflictType: 'low_confidence',
                severity: 'high' as const,
                description: 'Low confidence mapping for "Operating Expenses"',
                sourceLabel: 'Operating Expenses',
                targetAddress: 'B15',
                suggestions: ['Map to Operating Expenses cell', 'Map to SG&A cell', 'Skip this item'],
                isResolved: false,
            },
            {
                id: '2',
                conflictType: 'missing_required',
                severity: 'critical' as const,
                description: 'Template cell "Interest Expense" has no mapping',
                sourceLabel: undefined,
                targetAddress: 'B20',
                suggestions: ['Search extracted data', 'Enter value manually', 'Mark as N/A'],
                isResolved: false,
            },
            {
                id: '3',
                conflictType: 'validation_failure',
                severity: 'medium' as const,
                description: 'Assets ($5.2M) ≠ Liabilities + Equity ($5.1M)',
                suggestions: ['Review balance sheet totals', 'Check for missing items'],
                isResolved: false,
            },
        ],
    };

    const data = mapping || mockMapping;

    const handleResolve = (conflictId: string, resolution: string) => {
        resolveConflict(conflictId);
        addNotification('success', 'Conflict resolved');
    };

    const unresolvedCount = data.conflicts.filter((c) => !c.isResolved).length;

    return (
        <div className="space-y-6 animate-fade-in">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold text-dark-100">Mapping Review</h1>
                    <p className="text-dark-400 mt-1">
                        Review and resolve mapping conflicts
                    </p>
                </div>
                <div className="flex items-center space-x-3">
                    <button
                        onClick={() => navigate('/audit')}
                        className="btn btn-secondary"
                    >
                        View Audit Trail
                    </button>
                    <button
                        className="btn btn-primary flex items-center space-x-2"
                        disabled={unresolvedCount > 0}
                    >
                        <Download className="w-4 h-4" />
                        <span>Export Excel</span>
                    </button>
                </div>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[
                    { label: 'Total Items', value: data.totalItems, color: 'text-dark-100' },
                    { label: 'Auto Mapped', value: data.autoMappedCount, color: 'text-green-400' },
                    { label: 'Avg Confidence', value: `${(data.averageConfidence * 100).toFixed(0)}%`, color: 'text-primary-400' },
                    { label: 'Conflicts', value: unresolvedCount, color: unresolvedCount > 0 ? 'text-red-400' : 'text-green-400' },
                ].map((stat) => (
                    <div key={stat.label} className="card p-4">
                        <p className="text-sm text-dark-400">{stat.label}</p>
                        <p className={`text-2xl font-bold mt-1 ${stat.color}`}>{stat.value}</p>
                    </div>
                ))}
            </div>

            {/* Progress Bar */}
            <div className="card p-4">
                <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-dark-100">Mapping Progress</span>
                    <span className="text-sm text-dark-400">
                        {data.mappedCount} / {data.totalItems} items
                    </span>
                </div>
                <div className="h-2 bg-dark-700 rounded-full overflow-hidden">
                    <div
                        className="h-full bg-gradient-to-r from-primary-500 to-accent-500 transition-all duration-500"
                        style={{ width: `${(data.mappedCount / data.totalItems) * 100}%` }}
                    />
                </div>
            </div>

            {/* Conflicts */}
            <div className="card p-6">
                <h2 className="text-lg font-semibold text-dark-100 mb-4">
                    Conflicts to Review ({unresolvedCount})
                </h2>
                <div className="space-y-4">
                    {data.conflicts.map((conflict) => (
                        <ConflictItem
                            key={conflict.id}
                            conflict={conflict}
                            onResolve={handleResolve}
                        />
                    ))}
                </div>
            </div>

            {/* Continue Button */}
            {unresolvedCount === 0 && (
                <div className="card p-6 border-l-4 border-green-500 bg-green-500/5">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-3">
                            <CheckCircle className="w-6 h-6 text-green-500" />
                            <div>
                                <p className="font-medium text-dark-100">All Conflicts Resolved!</p>
                                <p className="text-sm text-dark-400">Ready to export your populated template</p>
                            </div>
                        </div>
                        <button className="btn btn-primary flex items-center space-x-2">
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
