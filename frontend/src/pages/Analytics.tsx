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

const Analytics: React.FC = () =& gt; {
    const [data, setData] = useState & lt; AnalyticsData | null & gt; (null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState & lt; string | null & gt; (null);
    const [timeRange, setTimeRange] = useState & lt; '7d' | '30d' | '90d' & gt; ('30d');

    useEffect(() =& gt; {
        fetchAnalytics();
    }, [timeRange]);

    const fetchAnalytics = async() =& gt; {
        try {
            setLoading(true);
            // TODO: Replace with actual API call when backend endpoint is ready
            // const response = await fetch(`/api/v1/analytics?range=${timeRange}`);
            // const data = await response.json();

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
                usage_by_day: Array.from({ length: 30 }, (_, i) =& gt; ({
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
}> = ({ icon, title, value, subtitle, trend }) =& gt; (
        & lt;div className = "bg-white rounded-xl shadow-sm border border-gray-200 p-6" & gt;
            & lt;div className = "flex items-center justify-between mb-4" & gt;
                & lt;div className = "p-2 bg-green-50 rounded-lg" & gt; { icon }& lt;/div&gt;
{
    trend & amp;& amp; (
                    & lt;span className = "text-sm text-green-600 flex items-center space-x-1" & gt;
                        & lt;TrendingUp className = "w-4 h-4" /& gt;
                        & lt; span & gt; { trend }& lt;/span&gt;
                    & lt;/span&gt;
                )
}
            & lt;/div&gt;
            & lt;h3 className = "text-sm font-medium text-gray-600 mb-1" & gt; { title }& lt;/h3&gt;
            & lt;p className = "text-3xl font-bold text-gray-900" & gt; { value }& lt;/p&gt;
{ subtitle & amp;& amp; & lt;p className = "text-sm text-gray-500 mt-1" & gt; { subtitle }& lt;/p&gt; }
        & lt;/div&gt;
    );

return (
        & lt;div className = "min-h-screen bg-gray-50 p-6" & gt;
            & lt;div className = "max-w-7xl mx-auto" & gt;
{/* Header */ }
                & lt;div className = "mb-8" & gt;
                    & lt;div className = "flex items-center justify-between" & gt;
                        & lt;div className = "flex items-center space-x-3" & gt;
                            & lt;BarChart3 className = "w-8 h-8 text-green-600" /& gt;
                            & lt;h1 className = "text-3xl font-bold text-gray-900" & gt;Analytics Dashboard & lt;/h1&gt;
                        & lt;/div&gt;
                        & lt;div className = "flex items-center space-x-3" & gt;
{/* Time Range Selector */ }
                            & lt; select
value = { timeRange }
onChange = {(e) =& gt; setTimeRange(e.target.value as '7d' | '30d' | '90d')}
className = "px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
    & gt;
                                & lt;option value = "7d" & gt;Last 7 days & lt;/option&gt;
                                & lt;option value = "30d" & gt;Last 30 days & lt;/option&gt;
                                & lt;option value = "90d" & gt;Last 90 days & lt;/option&gt;
                            & lt;/select&gt;
                            & lt; button
onClick = { fetchAnalytics }
className = "flex items-center space-x-2 px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
    & gt;
                                & lt;RefreshCw className = {`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /&gt;
                                & lt; span & gt; Refresh & lt;/span&gt;
                            & lt;/button&gt;
                        & lt;/div&gt;
                    & lt;/div&gt;
                    & lt;p className = "text-gray-600 mt-2" & gt;
                        Track usage, performance, and trends across your organization.
                    & lt;/p&gt;
                & lt;/div&gt;

{/* Error Alert */ }
{
    error & amp;& amp; (
                    & lt;div className = "mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center space-x-3" & gt;
                        & lt;AlertCircle className = "w-5 h-5 text-red-500" /& gt;
                        & lt;span className = "text-red-700" & gt; { error }& lt;/span&gt;
                    & lt;/div&gt;
                )
}

{
    loading ? (
                    & lt;div className = "flex items-center justify-center py-12" & gt;
                        & lt;RefreshCw className = "w-8 h-8 animate-spin text-green-600" /& gt;
                    & lt;/div&gt;
                ) : data ? (
                    & lt;& gt;
    {/* Stats Grid */ }
                        & lt;div className = "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8" & gt;
                            & lt; StatCard
    icon = {& lt;FileText className = "w-6 h-6 text-green-600" /& gt;
}
title = "Total Documents"
value = { data.total_documents.toLocaleString() }
subtitle = {`${data.documents_this_month} this month`}
trend = "+12%"
    /& gt;
                            & lt; StatCard
icon = {& lt;Download className = "w-6 h-6 text-green-600" /& gt;}
title = "Total Exports"
value = { data.total_exports.toLocaleString() }
subtitle = {`${data.exports_this_month} this month`}
trend = "+8%"
    /& gt;
                            & lt; StatCard
icon = {& lt;Users className = "w-6 h-6 text-green-600" /& gt;}
title = "Active Users"
value = { data.total_users }
subtitle = "Across all teams"
    /& gt;
                            & lt; StatCard
icon = {& lt;Calendar className = "w-6 h-6 text-green-600" /& gt;}
title = "Avg Processing Time"
value = {`${data.avg_processing_time}s`}
subtitle = "Per document"
trend = "-15%"
    /& gt;
                        & lt;/div&gt;

{/* Popular Templates */ }
                        & lt;div className = "bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8" & gt;
                            & lt;h2 className = "text-lg font-semibold text-gray-900 mb-4" & gt;
                                Most Used Templates
    & lt;/h2&gt;
                            & lt;div className = "space-y-4" & gt;
{
    data.popular_templates.map((template, index) =& gt; (
                                    & lt;div key = { index } className = "flex items-center justify-between" & gt;
                                        & lt;div className = "flex items-center space-x-3" & gt;
                                            & lt;div className = "w-8 h-8 bg-green-100 rounded-lg flex items-center justify-center text-green-600 font-semibold" & gt;
    { index + 1 }
                                            & lt;/div&gt;
                                            & lt;span className = "text-gray-900" & gt; { template.name }& lt;/span&gt;
                                        & lt;/div&gt;
                                        & lt;div className = "flex items-center space-x-4" & gt;
                                            & lt;span className = "text-gray-600" & gt; { template.count } uses & lt;/span&gt;
                                            & lt;div className = "w-32 bg-gray-200 rounded-full h-2" & gt;
                                                & lt; div
    className = "bg-green-500 h-2 rounded-full"
    style = {{
        width: `${(template.count / data.popular_templates[0].count) * 100}%`,
                                                    }
}
                                                & gt;& lt;/div&gt;
                                            & lt;/div&gt;
                                        & lt;/div&gt;
                                    & lt;/div&gt;
                                ))}
                            & lt;/div&gt;
                        & lt;/div&gt;

{/* Usage Chart Placeholder */ }
                        & lt;div className = "bg-white rounded-xl shadow-sm border border-gray-200 p-6" & gt;
                            & lt;h2 className = "text-lg font-semibold text-gray-900 mb-4" & gt;Usage Trends & lt;/h2&gt;
                            & lt;div className = "h-64 flex items-center justify-center border-2 border-dashed border-gray-300 rounded-lg" & gt;
                                & lt;div className = "text-center text-gray-500" & gt;
                                    & lt;BarChart3 className = "w-12 h-12 mx-auto mb-2 opacity-50" /& gt;
                                    & lt; p & gt;Chart visualization coming soon & lt;/p&gt;
                                    & lt;p className = "text-sm mt-1" & gt;
                                        Integrate with Chart.js or Recharts for interactive charts
    & lt;/p&gt;
                                & lt;/div&gt;
                            & lt;/div&gt;
                        & lt;/div&gt;
                    & lt;/&gt;
                ) : null}
            & lt;/div&gt;
        & lt;/div&gt;
    );
};

export default Analytics;
