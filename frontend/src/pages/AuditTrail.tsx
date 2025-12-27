import React, { useState, useEffect } from 'react';
import { History, FileText, GitMerge, Eye, Download, Filter, Loader2, RefreshCw } from 'lucide-react';
import { getAuditLog } from '../api/client';
import type { AuditEntry } from '../api/client';
import logo from '../assets/logo.png';

const AuditTrail: React.FC = () => {
    const [filter, setFilter] = useState<'all' | 'document' | 'mapping' | 'system'>('all');
    const [entries, setEntries] = useState<AuditEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [page, setPage] = useState(1);
    const [hasMore, setHasMore] = useState(false);
    const [total, setTotal] = useState(0);

    // Fetch audit log
    useEffect(() => {
        const fetchAuditLog = async () => {
            try {
                setLoading(true);
                const resourceType = filter === 'all' ? undefined : filter;
                const data = await getAuditLog(page, 20, resourceType);
                setEntries(data.entries || []);
                setTotal(data.total || 0);
                setHasMore(data.has_more || false);
            } catch (err) {
                console.error('Failed to fetch audit log:', err);
                // Use demo data on error
                setEntries([
                    {
                        id: '1',
                        timestamp: new Date().toISOString(),
                        action: 'system_start',
                        resource_type: 'system',
                        details: 'StatementXL API started',
                    },
                ]);
            } finally {
                setLoading(false);
            }
        };

        fetchAuditLog();
    }, [filter, page]);

    const getActionBadge = (action: string) => {
        if (action.includes('upload') || action.includes('create')) {
            return <span className="px-2 py-1 text-xs rounded-full bg-green-100 text-green-700">Create</span>;
        }
        if (action.includes('update') || action.includes('edit')) {
            return <span className="px-2 py-1 text-xs rounded-full bg-blue-100 text-blue-700">Update</span>;
        }
        if (action.includes('delete')) {
            return <span className="px-2 py-1 text-xs rounded-full bg-red-100 text-red-700">Delete</span>;
        }
        if (action.includes('resolve')) {
            return <span className="px-2 py-1 text-xs rounded-full bg-yellow-100 text-yellow-700">Resolved</span>;
        }
        return <span className="px-2 py-1 text-xs rounded-full bg-gray-100 text-gray-700">{action}</span>;
    };

    const getResourceIcon = (type: string) => {
        switch (type) {
            case 'document': return <FileText className="w-4 h-4 text-green-600" />;
            case 'mapping': return <GitMerge className="w-4 h-4 text-blue-600" />;
            default: return <History className="w-4 h-4 text-gray-500" />;
        }
    };

    const handleRefresh = () => {
        setPage(1);
        setLoading(true);
        setTimeout(() => {
            getAuditLog(1, 20, filter === 'all' ? undefined : filter)
                .then(data => {
                    setEntries(data.entries || []);
                    setTotal(data.total || 0);
                    setHasMore(data.has_more || false);
                })
                .finally(() => setLoading(false));
        }, 100);
    };

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
                            <h1 className="text-3xl font-bold">Audit Trail</h1>
                            <p className="text-green-100 mt-1">Complete history of all actions and changes</p>
                        </div>
                    </div>
                    <div className="flex items-center space-x-3">
                        <button
                            onClick={handleRefresh}
                            className="px-4 py-2 bg-white/20 text-white rounded-lg hover:bg-white/30 transition-colors flex items-center space-x-2"
                        >
                            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                            <span>Refresh</span>
                        </button>
                        <button className="px-4 py-2 bg-white text-green-600 rounded-lg hover:bg-green-50 transition-colors flex items-center space-x-2 font-medium shadow-sm">
                            <Download className="w-4 h-4" />
                            <span>Export JSON</span>
                        </button>
                    </div>
                </div>
            </div>

            {/* Filters */}
            <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm flex items-center space-x-4">
                <Filter className="w-5 h-5 text-gray-400" />
                <span className="text-sm text-gray-500">Filter:</span>
                {(['all', 'document', 'mapping', 'system'] as const).map((f) => (
                    <button
                        key={f}
                        onClick={() => { setFilter(f); setPage(1); }}
                        className={`
                            px-4 py-2 rounded-lg text-sm font-medium transition-all
                            ${filter === f
                                ? 'bg-green-100 text-green-700 border border-green-300'
                                : 'bg-gray-100 text-gray-600 border border-gray-200 hover:border-gray-300'
                            }
                        `}
                    >
                        {f.charAt(0).toUpperCase() + f.slice(1)}
                    </button>
                ))}
                <div className="flex-1" />
                <span className="text-sm text-gray-500">
                    {total} total entries
                </span>
            </div>

            {/* Loading state */}
            {loading && (
                <div className="flex items-center justify-center py-12">
                    <Loader2 className="w-8 h-8 text-green-600 animate-spin" />
                </div>
            )}

            {/* Audit Table */}
            {!loading && (
                <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
                    <table className="w-full">
                        <thead className="bg-green-50">
                            <tr>
                                <th className="px-6 py-3 text-left text-xs font-medium text-green-800 uppercase tracking-wider">Time</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-green-800 uppercase tracking-wider">Resource</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-green-800 uppercase tracking-wider">Action</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-green-800 uppercase tracking-wider">Details</th>
                                <th className="px-6 py-3 text-center text-xs font-medium text-green-800 uppercase tracking-wider">View</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                            {entries.length === 0 ? (
                                <tr>
                                    <td colSpan={5} className="px-6 py-12 text-center text-gray-500">
                                        No audit entries found
                                    </td>
                                </tr>
                            ) : (
                                entries.map((entry) => (
                                    <tr key={entry.id} className="hover:bg-green-50/50 transition-colors">
                                        <td className="px-6 py-4 text-sm text-gray-500">
                                            {new Date(entry.timestamp).toLocaleString()}
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className="flex items-center space-x-2">
                                                {getResourceIcon(entry.resource_type)}
                                                <span className="text-sm text-gray-700">
                                                    {entry.resource_type}
                                                    {entry.resource_id && ` (${entry.resource_id.slice(0, 8)}...)`}
                                                </span>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">
                                            {getActionBadge(entry.action)}
                                        </td>
                                        <td className="px-6 py-4 text-sm text-gray-600">
                                            {entry.details || '-'}
                                        </td>
                                        <td className="px-6 py-4 text-center">
                                            <button className="p-1.5 rounded-lg text-gray-400 hover:text-green-600 hover:bg-green-50 transition-colors">
                                                <Eye className="w-4 h-4" />
                                            </button>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Pagination */}
            {!loading && hasMore && (
                <div className="flex justify-center">
                    <button
                        onClick={() => setPage(page + 1)}
                        className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-500 transition-colors"
                    >
                        Load More
                    </button>
                </div>
            )}

            {/* Summary Stats */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
                    <p className="text-sm text-gray-500">Total Entries</p>
                    <p className="text-2xl font-bold text-gray-900 mt-1">{total}</p>
                </div>
                <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
                    <p className="text-sm text-gray-500">Documents</p>
                    <p className="text-2xl font-bold text-green-600 mt-1">
                        {entries.filter(e => e.resource_type === 'document').length}
                    </p>
                </div>
                <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
                    <p className="text-sm text-gray-500">Mappings</p>
                    <p className="text-2xl font-bold text-blue-600 mt-1">
                        {entries.filter(e => e.resource_type === 'mapping').length}
                    </p>
                </div>
                <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
                    <p className="text-sm text-gray-500">System Events</p>
                    <p className="text-2xl font-bold text-gray-700 mt-1">
                        {entries.filter(e => e.resource_type === 'system').length}
                    </p>
                </div>
            </div>
        </div>
    );
};

export default AuditTrail;
