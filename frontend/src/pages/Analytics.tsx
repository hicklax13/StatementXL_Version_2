import React, { useState, useEffect } from 'react';
import {
    BarChart3,
    TrendingUp,
    FileText,
    Users,
    Calendar,
    Download,
    RefreshCw,
    AlertCircle,
} from 'lucide-react';
import { getErrorMessage } from '../api/client';

interface AnalyticsData {
    total_documents: number;
    total_exports: number;
    total_users: number;
    documents_this_month: number;
    exports_this_month: number;
    avg_processing_time: number;
    popular_templates: Array<{
        name: string;
        count: number;
    }>;
    usage_by_day: Array<{
        date: string;
        documents: number;
        exports: number;
    }>;
}

const Analytics: React.FC = () => {
    const [data, setData] = useState<AnalyticsData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [timeRange, setTimeRange] = useState<'7d' | '30d' | '90d'>('30d');

    useEffect(() => {
        fetchAnalytics();
    }, [timeRange]);

    const fetchAnalytics = async () => {
        try {
            setLoading(true);
            // Mock data for now
            setData({
                total_documents: 1247,
                total_exports: 892,
                total_users: 45,
                documents_this_month: 156,
                exports_this_month: 124,
                avg_processing_time: 2.3,
                popular_templates: [
                    { name: 'Income Statement - Basic', count: 342 },
                    { name: 'Balance Sheet - Corporate', count: 289 },
                    { name: 'Cash Flow - Professional', count: 261 },
                ],
                usage_by_day: Array.from({ length: 30 }, (_, i) => ({
                    date: new Date(Date.now() - (29 - i) * 24 * 60 * 60 * 1000).toLocaleDateString(),
                    documents: Math.floor(Math.random() * 20) + 5,
                    exports: Math.floor(Math.random() * 15) + 3,
                })),
            });
            setError(null);
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setLoading(false);
        }
    };

    const StatCard: React.FC<{
        icon: React.ReactNode;
        title: string;
        value: string | number;
        subtitle?: string;
        trend?: string;
    }> = ({ icon, title, value, subtitle, trend }) => (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-4">
                <div className="p-2 bg-green-50 rounded-lg">{icon}</div>
                {trend && (
                    <span className="text-sm text-green-600 flex items-center space-x-1">
                        <TrendingUp className="w-4 h-4" />
                        <span>{trend}</span>
                    </span>
                )}
            </div>
            <h3 className="text-sm font-medium text-gray-600 mb-1">{title}</h3>
            <p className="text-3xl font-bold text-gray-900">{value}</p>
            {subtitle && <p className="text-sm text-gray-500 mt-1">{subtitle}</p>}
        </div>
    );

    return (
        <div className="min-h-screen bg-gray-50 p-6">
            <div className="max-w-7xl mx-auto">
                {/* Header */}
                <div className="mb-8">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-3">
                            <BarChart3 className="w-8 h-8 text-green-600" />
                            <h1 className="text-3xl font-bold text-gray-900">Analytics Dashboard</h1>
                        </div>
                        <div className="flex items-center space-x-3">
                            <select
                                value={timeRange}
                                onChange={(e) => setTimeRange(e.target.value as '7d' | '30d' | '90d')}
                                className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                                aria-label="Select time range"
                            >
                                <option value="7d">Last 7 days</option>
                                <option value="30d">Last 30 days</option>
                                <option value="90d">Last 90 days</option>
                            </select>
                            <button
                                onClick={fetchAnalytics}
                                className="flex items-center space-x-2 px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
                                aria-label="Refresh analytics"
                            >
                                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                                <span>Refresh</span>
                            </button>
                        </div>
                    </div>
                    <p className="text-gray-600 mt-2">
                        Track usage, performance, and trends across your organization.
                    </p>
                </div>

                {/* Error Alert */}
                {error && (
                    <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center space-x-3">
                        <AlertCircle className="w-5 h-5 text-red-500" />
                        <span className="text-red-700">{error}</span>
                    </div>
                )}

                {loading ? (
                    <div className="flex items-center justify-center py-12">
                        <RefreshCw className="w-8 h-8 animate-spin text-green-600" />
                    </div>
                ) : data ? (
                    <>
                        {/* Stats Grid */}
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                            <StatCard
                                icon={<FileText className="w-6 h-6 text-green-600" />}
                                title="Total Documents"
                                value={data.total_documents.toLocaleString()}
                                subtitle={`${data.documents_this_month} this month`}
                                trend="+12%"
                            />
                            <StatCard
                                icon={<Download className="w-6 h-6 text-green-600" />}
                                title="Total Exports"
                                value={data.total_exports.toLocaleString()}
                                subtitle={`${data.exports_this_month} this month`}
                                trend="+8%"
                            />
                            <StatCard
                                icon={<Users className="w-6 h-6 text-green-600" />}
                                title="Active Users"
                                value={data.total_users}
                                subtitle="Across all teams"
                            />
                            <StatCard
                                icon={<Calendar className="w-6 h-6 text-green-600" />}
                                title="Avg Processing Time"
                                value={`${data.avg_processing_time}s`}
                                subtitle="Per document"
                                trend="-15%"
                            />
                        </div>

                        {/* Popular Templates */}
                        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
                            <h2 className="text-lg font-semibold text-gray-900 mb-4">
                                Most Used Templates
                            </h2>
                            <div className="space-y-4">
                                {data.popular_templates.map((template, index) => (
                                    <div key={index} className="flex items-center justify-between">
                                        <div className="flex items-center space-x-3">
                                            <div className="w-8 h-8 bg-green-100 rounded-lg flex items-center justify-center text-green-600 font-semibold">
                                                {index + 1}
                                            </div>
                                            <span className="text-gray-900">{template.name}</span>
                                        </div>
                                        <div className="flex items-center space-x-4">
                                            <span className="text-gray-600">{template.count} uses</span>
                                            <div className="w-32 bg-gray-200 rounded-full h-2">
                                                <div
                                                    className="bg-green-500 h-2 rounded-full"
                                                    style={{
                                                        width: `${(template.count / data.popular_templates[0].count) * 100}%`,
                                                    }}
                                                ></div>
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Usage Chart Placeholder */}
                        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                            <h2 className="text-lg font-semibold text-gray-900 mb-4">Usage Trends</h2>
                            <div className="h-64 flex items-center justify-center border-2 border-dashed border-gray-300 rounded-lg">
                                <div className="text-center text-gray-500">
                                    <BarChart3 className="w-12 h-12 mx-auto mb-2 opacity-50" />
                                    <p>Chart visualization coming soon</p>
                                    <p className="text-sm mt-1">
                                        Integrate with Chart.js or Recharts for interactive charts
                                    </p>
                                </div>
                            </div>
                        </div>
                    </>
                ) : null}
            </div>
        </div>
    );
};

export default Analytics;
