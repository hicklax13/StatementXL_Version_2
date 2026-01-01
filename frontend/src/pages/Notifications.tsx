import React, { useState, useEffect } from 'react';
import {
    Bell,
    CheckCircle,
    AlertCircle,
    Info,
    AlertTriangle,
    Trash2,
    Check,
    RefreshCw,
} from 'lucide-react';
import { getErrorMessage } from '../api/client';

interface Notification {
    id: string;
    type: 'success' | 'error' | 'info' | 'warning';
    title: string;
    message: string;
    timestamp: string;
    read: boolean;
    action_url?: string;
}

const Notifications: React.FC = () => {
    const [notifications, setNotifications] = useState<Notification[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [filter, setFilter] = useState<'all' | 'unread'>('all');

    useEffect(() => {
        fetchNotifications();
    }, []);

    const fetchNotifications = async () => {
        try {
            setLoading(true);
            // Mock data for now
            setNotifications([
                {
                    id: '1',
                    type: 'success',
                    title: 'Document Processed',
                    message: 'Your Income Statement has been processed successfully.',
                    timestamp: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
                    read: false,
                },
                {
                    id: '2',
                    type: 'info',
                    title: 'New Feature Available',
                    message: 'Batch upload is now available. Upload multiple PDFs at once!',
                    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
                    read: true,
                },
                {
                    id: '3',
                    type: 'warning',
                    title: 'Low Document Quota',
                    message: 'You have 2 documents remaining this month.',
                    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(),
                    read: false,
                },
                {
                    id: '4',
                    type: 'error',
                    title: 'Processing Failed',
                    message: 'Unable to process "Financial_Report.pdf". Please try again.',
                    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 48).toISOString(),
                    read: true,
                },
            ]);
            setError(null);
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setLoading(false);
        }
    };

    const markAsRead = (id: string) => {
        setNotifications(prev =>
            prev.map(n => (n.id === id ? { ...n, read: true } : n))
        );
    };

    const markAllAsRead = () => {
        setNotifications(prev => prev.map(n => ({ ...n, read: true })));
    };

    const deleteNotification = (id: string) => {
        setNotifications(prev => prev.filter(n => n.id !== id));
    };

    const getIcon = (type: Notification['type']) => {
        switch (type) {
            case 'success':
                return <CheckCircle className="w-5 h-5 text-green-500" />;
            case 'error':
                return <AlertCircle className="w-5 h-5 text-red-500" />;
            case 'warning':
                return <AlertTriangle className="w-5 h-5 text-yellow-500" />;
            default:
                return <Info className="w-5 h-5 text-blue-500" />;
        }
    };

    const filteredNotifications = filter === 'unread'
        ? notifications.filter(n => !n.read)
        : notifications;

    const unreadCount = notifications.filter(n => !n.read).length;

    const formatTime = (timestamp: string) => {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now.getTime() - date.getTime();
        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);

        if (minutes < 60) return `${minutes}m ago`;
        if (hours < 24) return `${hours}h ago`;
        return `${days}d ago`;
    };

    return (
        <div className="min-h-screen bg-gray-50 p-6">
            <div className="max-w-3xl mx-auto">
                {/* Header */}
                <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center space-x-3">
                        <div className="relative">
                            <Bell className="w-8 h-8 text-green-600" />
                            {unreadCount > 0 && (
                                <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
                                    {unreadCount}
                                </span>
                            )}
                        </div>
                        <h1 className="text-3xl font-bold text-gray-900">Notifications</h1>
                    </div>
                    <div className="flex items-center space-x-3">
                        <select
                            value={filter}
                            onChange={(e) => setFilter(e.target.value as 'all' | 'unread')}
                            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500"
                            aria-label="Filter notifications"
                        >
                            <option value="all">All</option>
                            <option value="unread">Unread</option>
                        </select>
                        <button
                            onClick={markAllAsRead}
                            className="flex items-center space-x-2 px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
                        >
                            <Check className="w-4 h-4" />
                            <span>Mark all read</span>
                        </button>
                        <button
                            onClick={fetchNotifications}
                            className="p-2 hover:bg-gray-100 rounded-lg"
                            aria-label="Refresh notifications"
                        >
                            <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
                        </button>
                    </div>
                </div>

                {/* Error Alert */}
                {error && (
                    <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center space-x-3">
                        <AlertCircle className="w-5 h-5 text-red-500" />
                        <span className="text-red-700">{error}</span>
                    </div>
                )}

                {/* Notifications List */}
                <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                    {loading ? (
                        <div className="flex items-center justify-center py-12">
                            <RefreshCw className="w-8 h-8 animate-spin text-green-600" />
                        </div>
                    ) : filteredNotifications.length === 0 ? (
                        <div className="text-center py-12 text-gray-500">
                            <Bell className="w-12 h-12 mx-auto mb-3 opacity-50" />
                            <p>No notifications</p>
                        </div>
                    ) : (
                        <div className="divide-y divide-gray-100">
                            {filteredNotifications.map(notification => (
                                <div
                                    key={notification.id}
                                    className={`p-4 hover:bg-gray-50 transition-colors ${!notification.read ? 'bg-green-50/30' : ''
                                        }`}
                                >
                                    <div className="flex items-start space-x-4">
                                        <div className="flex-shrink-0 mt-1">
                                            {getIcon(notification.type)}
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center justify-between">
                                                <h3 className={`font-medium ${!notification.read ? 'text-gray-900' : 'text-gray-600'
                                                    }`}>
                                                    {notification.title}
                                                </h3>
                                                <span className="text-sm text-gray-400">
                                                    {formatTime(notification.timestamp)}
                                                </span>
                                            </div>
                                            <p className="text-gray-600 mt-1">{notification.message}</p>
                                        </div>
                                        <div className="flex items-center space-x-2">
                                            {!notification.read && (
                                                <button
                                                    onClick={() => markAsRead(notification.id)}
                                                    className="p-1.5 text-gray-400 hover:text-green-600 rounded-lg"
                                                    aria-label="Mark as read"
                                                >
                                                    <Check className="w-4 h-4" />
                                                </button>
                                            )}
                                            <button
                                                onClick={() => deleteNotification(notification.id)}
                                                className="p-1.5 text-gray-400 hover:text-red-600 rounded-lg"
                                                aria-label="Delete notification"
                                            >
                                                <Trash2 className="w-4 h-4" />
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default Notifications;
