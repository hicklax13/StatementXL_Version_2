import React, { useState, useEffect } from 'react';
import {
    Users,
    Shield,
    Activity,
    Server,
    Database,
    Lock,
    Unlock,
    Trash2,
    RefreshCw,
    AlertCircle,
    CheckCircle,
    XCircle,
} from 'lucide-react';
import {
    getAdminUsers,
    updateAdminUser,
    deleteAdminUser,
    getDetailedMetrics,
    getVersionInfo,
    getErrorMessage,
} from '../api/client';
import type { AdminUserResponse, DetailedMetricsResponse } from '../api/client';

type TabType = 'users' | 'metrics';

const AdminDashboard: React.FC = () => {
    const [activeTab, setActiveTab] = useState<TabType>('users');
    const [users, setUsers] = useState<AdminUserResponse[]>([]);
    const [metrics, setMetrics] = useState<DetailedMetricsResponse | null>(null);
    const [versionInfo, setVersionInfo] = useState<{
        version: string;
        build_number: string | null;
        git_commit: string | null;
        environment: string;
    } | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedUser, setSelectedUser] = useState<AdminUserResponse | null>(null);
    const [showDeleteModal, setShowDeleteModal] = useState(false);
    const [includeInactive, setIncludeInactive] = useState(false);

    const fetchUsers = async () => {
        try {
            setLoading(true);
            const response = await getAdminUsers(1, 50, includeInactive);
            setUsers(response.users);
            setError(null);
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setLoading(false);
        }
    };

    const fetchMetrics = async () => {
        try {
            setLoading(true);
            const [metricsData, version] = await Promise.all([
                getDetailedMetrics(),
                getVersionInfo(),
            ]);
            setMetrics(metricsData);
            setVersionInfo(version);
            setError(null);
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (activeTab === 'users') {
            fetchUsers();
        } else {
            fetchMetrics();
        }
    }, [activeTab, includeInactive]);

    const handleRoleChange = async (userId: string, newRole: AdminUserResponse['role']) => {
        try {
            await updateAdminUser(userId, { role: newRole });
            await fetchUsers();
        } catch (err) {
            setError(getErrorMessage(err));
        }
    };

    const handleToggleActive = async (userId: string, isActive: boolean) => {
        try {
            await updateAdminUser(userId, { is_active: !isActive });
            await fetchUsers();
        } catch (err) {
            setError(getErrorMessage(err));
        }
    };

    const handleUnlock = async (userId: string) => {
        try {
            await updateAdminUser(userId, { is_active: true });
            await fetchUsers();
        } catch (err) {
            setError(getErrorMessage(err));
        }
    };

    const handleDelete = async () => {
        if (!selectedUser) return;
        try {
            await deleteAdminUser(selectedUser.id);
            setShowDeleteModal(false);
            setSelectedUser(null);
            await fetchUsers();
        } catch (err) {
            setError(getErrorMessage(err));
        }
    };

    const formatUptime = (seconds: number): string => {
        const days = Math.floor(seconds / 86400);
        const hours = Math.floor((seconds % 86400) / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        if (days > 0) return `${days}d ${hours}h ${minutes}m`;
        if (hours > 0) return `${hours}h ${minutes}m`;
        return `${minutes}m`;
    };

    const getRoleColor = (role: string): string => {
        switch (role) {
            case 'admin':
                return 'bg-red-100 text-red-800';
            case 'analyst':
                return 'bg-blue-100 text-blue-800';
            case 'viewer':
                return 'bg-gray-100 text-gray-800';
            case 'api_user':
                return 'bg-purple-100 text-purple-800';
            default:
                return 'bg-gray-100 text-gray-800';
        }
    };

    return (
        <div className="min-h-screen bg-gray-50 p-6">
            <div className="max-w-7xl mx-auto">
                {/* Header */}
                <div className="mb-8">
                    <div className="flex items-center space-x-3">
                        <Shield className="w-8 h-8 text-green-600" />
                        <h1 className="text-3xl font-bold text-gray-900">Admin Dashboard</h1>
                    </div>
                    <p className="text-gray-600 mt-2">
                        Manage users, view system metrics, and monitor application health.
                    </p>
                </div>

                {/* Error Alert */}
                {error && (
                    <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center space-x-3">
                        <AlertCircle className="w-5 h-5 text-red-500" />
                        <span className="text-red-700">{error}</span>
                        <button
                            onClick={() => setError(null)}
                            className="ml-auto text-red-500 hover:text-red-700"
                        >
                            <XCircle className="w-5 h-5" />
                        </button>
                    </div>
                )}

                {/* Tabs */}
                <div className="mb-6 border-b border-gray-200">
                    <nav className="flex space-x-8">
                        <button
                            onClick={() => setActiveTab('users')}
                            className={`py-4 px-1 border-b-2 font-medium text-sm flex items-center space-x-2 ${
                                activeTab === 'users'
                                    ? 'border-green-500 text-green-600'
                                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                            }`}
                        >
                            <Users className="w-5 h-5" />
                            <span>User Management</span>
                        </button>
                        <button
                            onClick={() => setActiveTab('metrics')}
                            className={`py-4 px-1 border-b-2 font-medium text-sm flex items-center space-x-2 ${
                                activeTab === 'metrics'
                                    ? 'border-green-500 text-green-600'
                                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                            }`}
                        >
                            <Activity className="w-5 h-5" />
                            <span>System Metrics</span>
                        </button>
                    </nav>
                </div>

                {/* Users Tab */}
                {activeTab === 'users' && (
                    <div className="bg-white rounded-xl shadow-sm border border-gray-200">
                        {/* Toolbar */}
                        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
                            <div className="flex items-center space-x-4">
                                <label className="flex items-center space-x-2 text-sm text-gray-600">
                                    <input
                                        type="checkbox"
                                        checked={includeInactive}
                                        onChange={(e) => setIncludeInactive(e.target.checked)}
                                        className="rounded border-gray-300 text-green-600 focus:ring-green-500"
                                    />
                                    <span>Show inactive users</span>
                                </label>
                            </div>
                            <button
                                onClick={fetchUsers}
                                className="flex items-center space-x-2 px-3 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg"
                            >
                                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                                <span>Refresh</span>
                            </button>
                        </div>

                        {/* Users Table */}
                        <div className="overflow-x-auto">
                            <table className="w-full">
                                <thead className="bg-gray-50">
                                    <tr>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            User
                                        </th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            Role
                                        </th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            Status
                                        </th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            Last Login
                                        </th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            Actions
                                        </th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-200">
                                    {loading ? (
                                        <tr>
                                            <td colSpan={5} className="px-6 py-8 text-center text-gray-500">
                                                <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" />
                                                Loading users...
                                            </td>
                                        </tr>
                                    ) : users.length === 0 ? (
                                        <tr>
                                            <td colSpan={5} className="px-6 py-8 text-center text-gray-500">
                                                No users found.
                                            </td>
                                        </tr>
                                    ) : (
                                        users.map((user) => (
                                            <tr key={user.id} className={!user.is_active ? 'bg-gray-50' : ''}>
                                                <td className="px-6 py-4 whitespace-nowrap">
                                                    <div>
                                                        <div className="text-sm font-medium text-gray-900">
                                                            {user.full_name || 'No name'}
                                                        </div>
                                                        <div className="text-sm text-gray-500">{user.email}</div>
                                                    </div>
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap">
                                                    <select
                                                        value={user.role}
                                                        onChange={(e) =>
                                                            handleRoleChange(
                                                                user.id,
                                                                e.target.value as AdminUserResponse['role']
                                                            )
                                                        }
                                                        className={`text-xs font-semibold px-2.5 py-1 rounded-full border-0 ${getRoleColor(
                                                            user.role
                                                        )}`}
                                                    >
                                                        <option value="admin">Admin</option>
                                                        <option value="analyst">Analyst</option>
                                                        <option value="viewer">Viewer</option>
                                                        <option value="api_user">API User</option>
                                                    </select>
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap">
                                                    <div className="flex items-center space-x-2">
                                                        {user.is_active ? (
                                                            <span className="flex items-center space-x-1 text-green-600">
                                                                <CheckCircle className="w-4 h-4" />
                                                                <span className="text-sm">Active</span>
                                                            </span>
                                                        ) : (
                                                            <span className="flex items-center space-x-1 text-gray-500">
                                                                <XCircle className="w-4 h-4" />
                                                                <span className="text-sm">Inactive</span>
                                                            </span>
                                                        )}
                                                        {user.locked_until && (
                                                            <span className="flex items-center space-x-1 text-red-600">
                                                                <Lock className="w-4 h-4" />
                                                                <span className="text-sm">Locked</span>
                                                            </span>
                                                        )}
                                                        {!user.is_verified && (
                                                            <span className="text-xs text-yellow-600 bg-yellow-50 px-2 py-0.5 rounded">
                                                                Unverified
                                                            </span>
                                                        )}
                                                    </div>
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                                    {user.last_login
                                                        ? new Date(user.last_login).toLocaleDateString()
                                                        : 'Never'}
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap">
                                                    <div className="flex items-center space-x-2">
                                                        <button
                                                            onClick={() => handleToggleActive(user.id, user.is_active)}
                                                            className={`p-1.5 rounded-lg ${
                                                                user.is_active
                                                                    ? 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
                                                                    : 'text-green-600 hover:text-green-700 hover:bg-green-50'
                                                            }`}
                                                            title={user.is_active ? 'Deactivate' : 'Activate'}
                                                        >
                                                            {user.is_active ? (
                                                                <XCircle className="w-5 h-5" />
                                                            ) : (
                                                                <CheckCircle className="w-5 h-5" />
                                                            )}
                                                        </button>
                                                        {user.locked_until && (
                                                            <button
                                                                onClick={() => handleUnlock(user.id)}
                                                                className="p-1.5 rounded-lg text-yellow-600 hover:text-yellow-700 hover:bg-yellow-50"
                                                                title="Unlock account"
                                                            >
                                                                <Unlock className="w-5 h-5" />
                                                            </button>
                                                        )}
                                                        <button
                                                            onClick={() => {
                                                                setSelectedUser(user);
                                                                setShowDeleteModal(true);
                                                            }}
                                                            className="p-1.5 rounded-lg text-red-500 hover:text-red-700 hover:bg-red-50"
                                                            title="Delete user"
                                                        >
                                                            <Trash2 className="w-5 h-5" />
                                                        </button>
                                                    </div>
                                                </td>
                                            </tr>
                                        ))
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {/* Metrics Tab */}
                {activeTab === 'metrics' && (
                    <div className="space-y-6">
                        {/* Version Info */}
                        {versionInfo && (
                            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center space-x-2">
                                    <Server className="w-5 h-5 text-green-600" />
                                    <span>Application Info</span>
                                </h3>
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                    <div>
                                        <span className="text-sm text-gray-500">Version</span>
                                        <p className="text-lg font-medium text-gray-900">
                                            {versionInfo.version}
                                        </p>
                                    </div>
                                    <div>
                                        <span className="text-sm text-gray-500">Environment</span>
                                        <p className="text-lg font-medium text-gray-900 capitalize">
                                            {versionInfo.environment}
                                        </p>
                                    </div>
                                    <div>
                                        <span className="text-sm text-gray-500">Build Number</span>
                                        <p className="text-lg font-medium text-gray-900">
                                            {versionInfo.build_number || 'N/A'}
                                        </p>
                                    </div>
                                    <div>
                                        <span className="text-sm text-gray-500">Git Commit</span>
                                        <p className="text-lg font-medium text-gray-900 font-mono">
                                            {versionInfo.git_commit?.slice(0, 7) || 'N/A'}
                                        </p>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* System Metrics */}
                        {metrics && (
                            <>
                                <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                                    <div className="flex items-center justify-between mb-4">
                                        <h3 className="text-lg font-semibold text-gray-900 flex items-center space-x-2">
                                            <Activity className="w-5 h-5 text-green-600" />
                                            <span>System Resources</span>
                                        </h3>
                                        <button
                                            onClick={fetchMetrics}
                                            className="flex items-center space-x-2 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg"
                                        >
                                            <RefreshCw
                                                className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`}
                                            />
                                            <span>Refresh</span>
                                        </button>
                                    </div>
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                                        {/* CPU */}
                                        <div>
                                            <div className="flex items-center justify-between mb-2">
                                                <span className="text-sm text-gray-500">CPU Usage</span>
                                                <span className="text-sm font-medium text-gray-900">
                                                    {metrics.system.cpu_percent.toFixed(1)}%
                                                </span>
                                            </div>
                                            <div className="w-full bg-gray-200 rounded-full h-2">
                                                <div
                                                    className={`h-2 rounded-full ${
                                                        metrics.system.cpu_percent > 80
                                                            ? 'bg-red-500'
                                                            : metrics.system.cpu_percent > 60
                                                            ? 'bg-yellow-500'
                                                            : 'bg-green-500'
                                                    }`}
                                                    style={{ width: `${metrics.system.cpu_percent}%` }}
                                                ></div>
                                            </div>
                                        </div>

                                        {/* Memory */}
                                        <div>
                                            <div className="flex items-center justify-between mb-2">
                                                <span className="text-sm text-gray-500">Memory</span>
                                                <span className="text-sm font-medium text-gray-900">
                                                    {metrics.system.memory_percent.toFixed(1)}%
                                                </span>
                                            </div>
                                            <div className="w-full bg-gray-200 rounded-full h-2">
                                                <div
                                                    className={`h-2 rounded-full ${
                                                        metrics.system.memory_percent > 80
                                                            ? 'bg-red-500'
                                                            : metrics.system.memory_percent > 60
                                                            ? 'bg-yellow-500'
                                                            : 'bg-green-500'
                                                    }`}
                                                    style={{ width: `${metrics.system.memory_percent}%` }}
                                                ></div>
                                            </div>
                                            <p className="text-xs text-gray-400 mt-1">
                                                {metrics.system.memory_used_mb.toFixed(0)} /{' '}
                                                {metrics.system.memory_total_mb.toFixed(0)} MB
                                            </p>
                                        </div>

                                        {/* Disk */}
                                        <div>
                                            <div className="flex items-center justify-between mb-2">
                                                <span className="text-sm text-gray-500">Disk</span>
                                                <span className="text-sm font-medium text-gray-900">
                                                    {metrics.system.disk_percent.toFixed(1)}%
                                                </span>
                                            </div>
                                            <div className="w-full bg-gray-200 rounded-full h-2">
                                                <div
                                                    className={`h-2 rounded-full ${
                                                        metrics.system.disk_percent > 90
                                                            ? 'bg-red-500'
                                                            : metrics.system.disk_percent > 70
                                                            ? 'bg-yellow-500'
                                                            : 'bg-green-500'
                                                    }`}
                                                    style={{ width: `${metrics.system.disk_percent}%` }}
                                                ></div>
                                            </div>
                                            <p className="text-xs text-gray-400 mt-1">
                                                {metrics.system.disk_used_gb.toFixed(1)} /{' '}
                                                {metrics.system.disk_total_gb.toFixed(1)} GB
                                            </p>
                                        </div>

                                        {/* Uptime */}
                                        <div>
                                            <div className="flex items-center justify-between mb-2">
                                                <span className="text-sm text-gray-500">Uptime</span>
                                            </div>
                                            <p className="text-2xl font-semibold text-gray-900">
                                                {formatUptime(metrics.system.uptime_seconds)}
                                            </p>
                                        </div>
                                    </div>
                                </div>

                                {/* Database Stats */}
                                <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                                    <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center space-x-2">
                                        <Database className="w-5 h-5 text-green-600" />
                                        <span>Database</span>
                                    </h3>
                                    <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
                                        <div>
                                            <span className="text-sm text-gray-500">Pool Size</span>
                                            <p className="text-2xl font-semibold text-gray-900">
                                                {metrics.database.pool_size}
                                            </p>
                                        </div>
                                        <div>
                                            <span className="text-sm text-gray-500">
                                                Active Connections
                                            </span>
                                            <p className="text-2xl font-semibold text-gray-900">
                                                {metrics.database.active_connections}
                                            </p>
                                        </div>
                                        <div>
                                            <span className="text-sm text-gray-500">Process Memory</span>
                                            <p className="text-2xl font-semibold text-gray-900">
                                                {metrics.system.process_memory_mb.toFixed(1)} MB
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            </>
                        )}

                        {loading && (
                            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8 text-center">
                                <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-2 text-green-600" />
                                <p className="text-gray-500">Loading metrics...</p>
                            </div>
                        )}
                    </div>
                )}

                {/* Delete Confirmation Modal */}
                {showDeleteModal && selectedUser && (
                    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                        <div className="bg-white rounded-xl shadow-xl p-6 max-w-md w-full mx-4">
                            <h3 className="text-lg font-semibold text-gray-900 mb-2">
                                Delete User
                            </h3>
                            <p className="text-gray-600 mb-4">
                                Are you sure you want to delete{' '}
                                <strong>{selectedUser.email}</strong>? This action cannot be
                                undone.
                            </p>
                            <div className="flex justify-end space-x-3">
                                <button
                                    onClick={() => {
                                        setShowDeleteModal(false);
                                        setSelectedUser(null);
                                    }}
                                    className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={handleDelete}
                                    className="px-4 py-2 bg-red-600 text-white hover:bg-red-700 rounded-lg"
                                >
                                    Delete
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default AdminDashboard;
