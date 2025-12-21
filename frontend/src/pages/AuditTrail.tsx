import React, { useState } from 'react';
import { History, FileText, GitMerge, ArrowRight, Eye, Download, Filter } from 'lucide-react';

interface AuditEntry {
    id: string;
    timestamp: string;
    action: string;
    source: {
        type: 'pdf' | 'template' | 'manual';
        filename?: string;
        page?: number;
        cell?: string;
    };
    target: {
        sheet: string;
        cell: string;
        label: string;
    };
    value: string;
    confidence: number;
    user?: string;
}

const AuditTrail: React.FC = () => {
    const [filter, setFilter] = useState<'all' | 'auto' | 'manual'>('all');
    const [selectedEntry, setSelectedEntry] = useState<AuditEntry | null>(null);

    // Mock audit data
    const auditEntries: AuditEntry[] = [
        {
            id: '1',
            timestamp: '2024-12-20T10:30:00Z',
            action: 'auto_mapped',
            source: { type: 'pdf', filename: 'Income_Statement.pdf', page: 1 },
            target: { sheet: 'Model', cell: 'B5', label: 'Revenue' },
            value: '5,234,000',
            confidence: 0.98,
        },
        {
            id: '2',
            timestamp: '2024-12-20T10:30:01Z',
            action: 'auto_mapped',
            source: { type: 'pdf', filename: 'Income_Statement.pdf', page: 1 },
            target: { sheet: 'Model', cell: 'B6', label: 'COGS' },
            value: '2,456,000',
            confidence: 0.95,
        },
        {
            id: '3',
            timestamp: '2024-12-20T10:32:15Z',
            action: 'manual_edit',
            source: { type: 'manual' },
            target: { sheet: 'Model', cell: 'B10', label: 'Operating Expenses' },
            value: '1,234,500',
            confidence: 1.0,
            user: 'analyst@company.com',
        },
        {
            id: '4',
            timestamp: '2024-12-20T10:33:00Z',
            action: 'conflict_resolved',
            source: { type: 'template', cell: 'B15' },
            target: { sheet: 'Model', cell: 'B15', label: 'Interest Expense' },
            value: '45,000',
            confidence: 0.85,
            user: 'analyst@company.com',
        },
    ];

    const filteredEntries = auditEntries.filter((entry) => {
        if (filter === 'all') return true;
        if (filter === 'auto') return entry.action === 'auto_mapped';
        if (filter === 'manual') return entry.action !== 'auto_mapped';
        return true;
    });

    const getActionBadge = (action: string) => {
        switch (action) {
            case 'auto_mapped':
                return <span className="px-2 py-1 text-xs rounded-full bg-green-500/10 text-green-400">Auto</span>;
            case 'manual_edit':
                return <span className="px-2 py-1 text-xs rounded-full bg-blue-500/10 text-blue-400">Manual</span>;
            case 'conflict_resolved':
                return <span className="px-2 py-1 text-xs rounded-full bg-yellow-500/10 text-yellow-400">Resolved</span>;
            default:
                return <span className="px-2 py-1 text-xs rounded-full bg-dark-600 text-dark-300">{action}</span>;
        }
    };

    const getSourceIcon = (type: string) => {
        switch (type) {
            case 'pdf': return <FileText className="w-4 h-4 text-primary-400" />;
            case 'template': return <GitMerge className="w-4 h-4 text-accent-400" />;
            default: return <History className="w-4 h-4 text-dark-400" />;
        }
    };

    return (
        <div className="space-y-6 animate-fade-in">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold text-dark-100">Audit Trail</h1>
                    <p className="text-dark-400 mt-1">
                        Complete history of data mappings and changes
                    </p>
                </div>
                <button className="btn btn-secondary flex items-center space-x-2">
                    <Download className="w-4 h-4" />
                    <span>Export JSON</span>
                </button>
            </div>

            {/* Filters */}
            <div className="card p-4 flex items-center space-x-4">
                <Filter className="w-5 h-5 text-dark-400" />
                <span className="text-sm text-dark-400">Filter:</span>
                {['all', 'auto', 'manual'].map((f) => (
                    <button
                        key={f}
                        onClick={() => setFilter(f as any)}
                        className={`
              px-4 py-2 rounded-lg text-sm font-medium transition-all
              ${filter === f
                                ? 'bg-primary-500/20 text-primary-400 border border-primary-500'
                                : 'bg-dark-700 text-dark-300 border border-dark-600 hover:border-dark-500'
                            }
            `}
                    >
                        {f.charAt(0).toUpperCase() + f.slice(1)}
                    </button>
                ))}
                <div className="flex-1" />
                <span className="text-sm text-dark-400">
                    {filteredEntries.length} entries
                </span>
            </div>

            {/* Audit Table */}
            <div className="card overflow-hidden">
                <table className="w-full">
                    <thead className="table-header">
                        <tr>
                            <th className="px-6 py-3 text-left">Time</th>
                            <th className="px-6 py-3 text-left">Source</th>
                            <th className="px-6 py-3 text-center">→</th>
                            <th className="px-6 py-3 text-left">Target</th>
                            <th className="px-6 py-3 text-right">Value</th>
                            <th className="px-6 py-3 text-center">Confidence</th>
                            <th className="px-6 py-3 text-center">Type</th>
                            <th className="px-6 py-3 text-center">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filteredEntries.map((entry) => (
                            <tr
                                key={entry.id}
                                className="table-row cursor-pointer"
                                onClick={() => setSelectedEntry(entry)}
                            >
                                <td className="px-6 py-4 text-sm text-dark-400">
                                    {new Date(entry.timestamp).toLocaleTimeString()}
                                </td>
                                <td className="px-6 py-4">
                                    <div className="flex items-center space-x-2">
                                        {getSourceIcon(entry.source.type)}
                                        <span className="text-sm text-dark-200">
                                            {entry.source.filename || entry.source.type}
                                            {entry.source.page && ` (p${entry.source.page})`}
                                        </span>
                                    </div>
                                </td>
                                <td className="px-6 py-4 text-center">
                                    <ArrowRight className="w-4 h-4 text-dark-500 mx-auto" />
                                </td>
                                <td className="px-6 py-4">
                                    <div>
                                        <p className="text-sm font-medium text-dark-100">{entry.target.label}</p>
                                        <p className="text-xs text-dark-400">
                                            {entry.target.sheet}!{entry.target.cell}
                                        </p>
                                    </div>
                                </td>
                                <td className="px-6 py-4 text-right font-mono text-dark-100">
                                    {entry.value}
                                </td>
                                <td className="px-6 py-4 text-center">
                                    <span className={`text-sm font-medium ${entry.confidence >= 0.9 ? 'text-green-400' :
                                            entry.confidence >= 0.7 ? 'text-yellow-400' : 'text-red-400'
                                        }`}>
                                        {(entry.confidence * 100).toFixed(0)}%
                                    </span>
                                </td>
                                <td className="px-6 py-4 text-center">
                                    {getActionBadge(entry.action)}
                                </td>
                                <td className="px-6 py-4 text-center">
                                    <button className="p-1.5 rounded-lg text-dark-400 hover:text-primary-400 hover:bg-primary-500/10 transition-colors">
                                        <Eye className="w-4 h-4" />
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Summary Stats */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {[
                    { label: 'Total Changes', value: auditEntries.length },
                    { label: 'Auto Mapped', value: auditEntries.filter(e => e.action === 'auto_mapped').length },
                    { label: 'Manual Edits', value: auditEntries.filter(e => e.action === 'manual_edit').length },
                    { label: 'Conflicts Resolved', value: auditEntries.filter(e => e.action === 'conflict_resolved').length },
                ].map((stat) => (
                    <div key={stat.label} className="card p-4">
                        <p className="text-sm text-dark-400">{stat.label}</p>
                        <p className="text-2xl font-bold text-dark-100 mt-1">{stat.value}</p>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default AuditTrail;
