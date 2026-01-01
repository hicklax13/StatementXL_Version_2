import React, { useState } from 'react';
import {
    Search as SearchIcon,
    FileText,
    Calendar,
    Filter,
    Download,
    Eye,
    RefreshCw,
} from 'lucide-react';
import { getErrorMessage } from '../api/client';

interface SearchResult {
    id: string;
    type: 'document' | 'template' | 'export';
    title: string;
    description: string;
    date: string;
    status?: string;
}

const Search: React.FC = () => {
    const [query, setQuery] = useState('');
    const [results, setResults] = useState<SearchResult[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [filters, setFilters] = useState({
        type: 'all',
        dateRange: '30d',
    });

    const handleSearch = async () => {
        if (!query.trim()) return;

        try {
            setLoading(true);
            setError(null);

            // TODO: Replace with actual API call
            // const response = await fetch(`/api/v1/search?q=${query}&type=${filters.type}`);
            // const data = await response.json();

            // Mock results
            setResults([
                {
                    id: '1',
                    type: 'document',
                    title: 'Q4 2024 Income Statement',
                    description: 'Uploaded on Dec 15, 2024 • Processed successfully',
                    date: '2024-12-15',
                    status: 'completed',
                },
                {
                    id: '2',
                    type: 'template',
                    title: 'Balance Sheet - Corporate',
                    description: 'Professional template with advanced formulas',
                    date: '2024-11-20',
                },
                {
                    id: '3',
                    type: 'export',
                    title: 'Annual_Report_2024.xlsx',
                    description: 'Exported from Income Statement template',
                    date: '2024-12-10',
                    status: 'ready',
                },
            ]);
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setLoading(false);
        }
    };

    const getTypeIcon = (type: string) => {
        switch (type) {
            case 'document':
                return <FileText className="w-5 h-5 text-blue-600" />;
            case 'template':
                return <FileText className="w-5 h-5 text-green-600" />;
            case 'export':
                return <Download className="w-5 h-5 text-purple-600" />;
            default:
                return <FileText className="w-5 h-5 text-gray-600" />;
        }
    };

    const getTypeBadge = (type: string) => {
        switch (type) {
            case 'document':
                return 'bg-blue-100 text-blue-800';
            case 'template':
                return 'bg-green-100 text-green-800';
            case 'export':
                return 'bg-purple-100 text-purple-800';
            default:
                return 'bg-gray-100 text-gray-800';
        }
    };

    return (
        <div className="min-h-screen bg-gray-50 p-6">
            <div className="max-w-5xl mx-auto">
                {/* Header */}
                <div className="mb-8">
                    <div className="flex items-center space-x-3 mb-4">
                        <SearchIcon className="w-8 h-8 text-green-600" />
                        <h1 className="text-3xl font-bold text-gray-900">Search</h1>
                    </div>
                    <p className="text-gray-600">
                        Find documents, templates, and exports across your workspace
                    </p>
                </div>

                {/* Search Bar */}
                <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
                    <div className="flex items-center space-x-4">
                        <div className="flex-1 relative">
                            <SearchIcon className="absolute left-4 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                            <input
                                type="text"
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                                placeholder="Search for documents, templates, or exports..."
                                className="w-full pl-12 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                            />
                        </div>
                        <button
                            onClick={handleSearch}
                            disabled={!query.trim() || loading}
                            className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
                        >
                            {loading ? (
                                <>
                                    <RefreshCw className="w-5 h-5 animate-spin" />
                                    <span>Searching...</span>
                                </>
                            ) : (
                                <>
                                    <SearchIcon className="w-5 h-5" />
                                    <span>Search</span>
                                </>
                            )}
                        </button>
                    </div>

                    {/* Filters */}
                    <div className="flex items-center space-x-4 mt-4 pt-4 border-t border-gray-200">
                        <div className="flex items-center space-x-2">
                            <Filter className="w-4 h-4 text-gray-500" />
                            <span className="text-sm text-gray-600">Filters:</span>
                        </div>
                        <select
                            value={filters.type}
                            onChange={(e) => setFilters({ ...filters, type: e.target.value })}
                            className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-green-500 focus:border-transparent"
                            aria-label="Filter by type"
                        >
                            <option value="all">All Types</option>
                            <option value="document">Documents</option>
                            <option value="template">Templates</option>
                            <option value="export">Exports</option>
                        </select>
                        <select
                            value={filters.dateRange}
                            onChange={(e) => setFilters({ ...filters, dateRange: e.target.value })}
                            className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-green-500 focus:border-transparent"
                            aria-label="Filter by date range"
                        >
                            <option value="7d">Last 7 days</option>
                            <option value="30d">Last 30 days</option>
                            <option value="90d">Last 90 days</option>
                            <option value="all">All time</option>
                        </select>
                    </div>
                </div>

                {/* Results */}
                {error && (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
                        <p className="text-red-700">{error}</p>
                    </div>
                )}

                {results.length > 0 ? (
                    <div className="space-y-3">
                        <div className="flex items-center justify-between mb-4">
                            <p className="text-sm text-gray-600">
                                Found {results.length} result{results.length !== 1 ? 's' : ''}
                            </p>
                        </div>
                        {results.map((result) => (
                            <div
                                key={result.id}
                                className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 hover:border-green-300 transition-colors cursor-pointer"
                            >
                                <div className="flex items-start justify-between">
                                    <div className="flex items-start space-x-4 flex-1">
                                        <div className="p-2 bg-gray-50 rounded-lg">
                                            {getTypeIcon(result.type)}
                                        </div>
                                        <div className="flex-1">
                                            <div className="flex items-center space-x-3 mb-2">
                                                <h3 className="text-lg font-semibold text-gray-900">
                                                    {result.title}
                                                </h3>
                                                <span
                                                    className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${getTypeBadge(
                                                        result.type
                                                    )}`}
                                                >
                                                    {result.type}
                                                </span>
                                                {result.status && (
                                                    <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-green-100 text-green-800">
                                                        {result.status}
                                                    </span>
                                                )}
                                            </div>
                                            <p className="text-gray-600 mb-2">{result.description}</p>
                                            <div className="flex items-center space-x-4 text-sm text-gray-500">
                                                <span className="flex items-center space-x-1">
                                                    <Calendar className="w-4 h-4" />
                                                    <span>{new Date(result.date).toLocaleDateString()}</span>
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                    <button className="p-2 text-gray-400 hover:text-green-600 hover:bg-green-50 rounded-lg" aria-label="View details">
                                        <Eye className="w-5 h-5" />
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                ) : query && !loading ? (
                    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center">
                        <SearchIcon className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                        <h3 className="text-lg font-semibold text-gray-900 mb-2">No results found</h3>
                        <p className="text-gray-600">
                            Try adjusting your search query or filters
                        </p>
                    </div>
                ) : !query ? (
                    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center">
                        <SearchIcon className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                        <h3 className="text-lg font-semibold text-gray-900 mb-2">
                            Start searching
                        </h3>
                        <p className="text-gray-600">
                            Enter a search term to find documents, templates, and exports
                        </p>
                    </div>
                ) : null}
            </div>
        </div>
    );
};

export default Search;
