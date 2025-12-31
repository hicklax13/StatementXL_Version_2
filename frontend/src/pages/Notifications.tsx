import React, { useState, useEffect } from 'react';
import {
    Bell,
    CheckCircle,
    AlertCircle,
    Info,
    X,
    Check,
    RefreshCw,
    Filter,
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

const Notifications: React.FC = () =& gt; {
    const [notifications, setNotifications] = useState & lt; Notification[] & gt; ([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState & lt; string | null & gt; (null);
    const [filter, setFilter] = useState & lt; 'all' | 'unread' & gt; ('all');

    useEffect(() =& gt; {
        fetchNotifications();
    }, []);

    const fetchNotifications = async() =& gt; {
        try {
            setLoading(true);
            // TODO: Replace with actual API call
            // const response = await fetch('/api/v1/notifications');
            // const data = await response.json();

            // Mock data
            setNotifications([
                {
                    id: '1',
                    type: 'success',
                    title: 'Document processed successfully',
                    message: 'Your Income Statement has been extracted and is ready for review.',
                    timestamp: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
                    read: false,
                    action_url: '/extraction-review/123',
                },
                {
                    id: '2',
                    type: 'info',
                    title: 'New template available',
                    message: 'Check out our new Balance Sheet - Professional template.',
                    timestamp: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
                    read: false,
                },
                {
                    id: '3',
                    type: 'success',
                    title: 'Export completed',
                    message: 'Your Excel file is ready for download.',
                    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
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

    const markAsRead = async (id: string) =& gt; {
        setNotifications(notifications.map(n =& gt; n.id === id ? { ...n, read: true } : n));
        // TODO: API call to mark as read
    };

    const markAllAsRead = async() =& gt; {
        setNotifications(notifications.map(n =& gt; ({ ...n, read: true })));
        // TODO: API call to mark all as read
    };

    const deleteNotification = async (id: string) =& gt; {
        setNotifications(notifications.filter(n =& gt; n.id !== id));
        // TODO: API call to delete
    };

    const getIcon = (type: Notification['type']) =& gt; {
        switch (type) {
            case 'success':
                return & lt;CheckCircle className = "w-6 h-6 text-green-600" /& gt;;
            case 'error':
                return & lt;AlertCircle className = "w-6 h-6 text-red-600" /& gt;;
            case 'warning':
                return & lt;AlertCircle className = "w-6 h-6 text-yellow-600" /& gt;;
            case 'info':
                return & lt;Info className = "w-6 h-6 text-blue-600" /& gt;;
        }
    };

    const filteredNotifications = filter === 'unread'
        ? notifications.filter(n =& gt; !n.read)
        : notifications;

    const unreadCount = notifications.filter(n =& gt; !n.read).length;

    return (
        & lt;div className = "min-h-screen bg-gray-50 p-6" & gt;
            & lt;div className = "max-w-4xl mx-auto" & gt;
    {/* Header */ }
                & lt;div className = "mb-8" & gt;
                    & lt;div className = "flex items-center justify-between" & gt;
                        & lt;div className = "flex items-center space-x-3" & gt;
                            & lt;Bell className = "w-8 h-8 text-green-600" /& gt;
                            & lt; div & gt;
                                & lt;h1 className = "text-3xl font-bold text-gray-900" & gt; Notifications & lt;/h1&gt;
    {
        unreadCount & gt; 0 & amp;& amp; (
                                    & lt;p className = "text-sm text-gray-600 mt-1" & gt;
        { unreadCount } unread notification{ unreadCount !== 1 ? 's' : '' }
                                    & lt;/p&gt;
                                )
    }
                            & lt;/div&gt;
                        & lt;/div&gt;
                        & lt;div className = "flex items-center space-x-3" & gt;
    {
        unreadCount & gt; 0 & amp;& amp; (
                                & lt; button
        onClick = { markAllAsRead }
        className = "flex items-center space-x-2 px-4 py-2 text-green-600 hover:bg-green-50 rounded-lg"
            & gt;
                                    & lt;Check className = "w-4 h-4" /& gt;
                                    & lt; span & gt;Mark all as read & lt;/span&gt;
                                & lt;/button&gt;
                            )
    }
                            & lt; button
    onClick = { fetchNotifications }
    className = "p-2 hover:bg-gray-100 rounded-lg"
        & gt;
                                & lt;RefreshCw className = {`w-5 h-5 ${loading ? 'animate-spin' : ''}`
} /&gt;
                            & lt;/button&gt;
                        & lt;/div&gt;
                    & lt;/div&gt;
                & lt;/div&gt;

{/* Filter */ }
                & lt;div className = "mb-6 flex items-center space-x-2" & gt;
                    & lt;Filter className = "w-5 h-5 text-gray-400" /& gt;
                    & lt; button
onClick = {() =& gt; setFilter('all')}
className = {`px-4 py-2 rounded-lg font-medium ${filter === 'all'
        ? 'bg-green-600 text-white'
        : 'bg-white text-gray-700 hover:bg-gray-50'
    }`}
                    & gt;
All
    & lt;/button&gt;
                    & lt; button
onClick = {() =& gt; setFilter('unread')}
className = {`px-4 py-2 rounded-lg font-medium ${filter === 'unread'
        ? 'bg-green-600 text-white'
        : 'bg-white text-gray-700 hover:bg-gray-50'
    }`}
                    & gt;
Unread({ unreadCount })
    & lt;/button&gt;
                & lt;/div&gt;

{/* Notifications List */ }
                & lt;div className = "space-y-3" & gt;
{
    loading ? (
                        & lt;div className = "flex items-center justify-center py-12" & gt;
                            & lt;RefreshCw className = "w-8 h-8 animate-spin text-green-600" /& gt;
                        & lt;/div&gt;
                    ) : filteredNotifications.length === 0 ? (
                        & lt;div className = "bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center" & gt;
                            & lt;Bell className = "w-16 h-16 text-gray-300 mx-auto mb-4" /& gt;
                            & lt;h3 className = "text-lg font-semibold text-gray-900 mb-2" & gt;
                                No notifications
        & lt;/h3&gt;
                            & lt;p className = "text-gray-600" & gt;
                                You're all caught up! We'll notify you when something important happens.
                            & lt;/p&gt;
                        & lt;/div&gt;
                    ) : (
        filteredNotifications.map((notification) =& gt; (
                            & lt; div
    key = { notification.id }
    className = {`bg-white rounded-xl shadow-sm border border-gray-200 p-6 transition-all ${!notification.read ? 'border-l-4 border-l-green-600' : ''
        }`
}
                            & gt;
                                & lt;div className = "flex items-start justify-between" & gt;
                                    & lt;div className = "flex items-start space-x-4 flex-1" & gt;
                                        & lt;div className = "flex-shrink-0 mt-1" & gt;
{ getIcon(notification.type) }
                                        & lt;/div&gt;
                                        & lt;div className = "flex-1 min-w-0" & gt;
                                            & lt;div className = "flex items-center space-x-2 mb-1" & gt;
                                                & lt;h3 className = "font-semibold text-gray-900" & gt;
{ notification.title }
                                                & lt;/h3&gt;
{
    !notification.read & amp;& amp; (
                                                    & lt;span className = "w-2 h-2 bg-green-600 rounded-full" & gt;& lt;/span&gt;
                                                )
}
                                            & lt;/div&gt;
                                            & lt;p className = "text-gray-600 mb-2" & gt; { notification.message }& lt;/p&gt;
                                            & lt;p className = "text-sm text-gray-500" & gt;
{ new Date(notification.timestamp).toLocaleString() }
                                            & lt;/p&gt;
{
    notification.action_url & amp;& amp; (
                                                & lt; a
    href = { notification.action_url }
    className = "inline-block mt-3 text-green-600 hover:text-green-700 font-medium text-sm"
        & gt;
                                                    View details →
                                                & lt;/a&gt;
                                            )
}
                                        & lt;/div&gt;
                                    & lt;/div&gt;
                                    & lt;div className = "flex items-center space-x-2 ml-4" & gt;
{
    !notification.read & amp;& amp; (
                                            & lt; button
    onClick = {() =& gt; markAsRead(notification.id)
}
className = "p-2 text-gray-400 hover:text-green-600 hover:bg-green-50 rounded-lg"
title = "Mark as read"
    & gt;
                                                & lt;Check className = "w-5 h-5" /& gt;
                                            & lt;/button&gt;
                                        )}
                                        & lt; button
onClick = {() =& gt; deleteNotification(notification.id)}
className = "p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg"
title = "Delete"
    & gt;
                                            & lt;X className = "w-5 h-5" /& gt;
                                        & lt;/button&gt;
                                    & lt;/div&gt;
                                & lt;/div&gt;
                            & lt;/div&gt;
                        ))
                    )}
                & lt;/div&gt;
            & lt;/div&gt;
        & lt;/div&gt;
    );
};

export default Notifications;
