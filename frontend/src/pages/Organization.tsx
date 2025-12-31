import React, { useState, useEffect } from 'react';
import {
    Building2,
    Users,
    Mail,
    UserPlus,
    Settings,
    Crown,
    Shield,
    Eye,
    Trash2,
    RefreshCw,
    AlertCircle,
} from 'lucide-react';
import { getErrorMessage } from '../api/client';

interface OrganizationMember {
    id: string;
    email: string;
    full_name: string | null;
    role: 'owner' | 'admin' | 'member' | 'viewer';
    joined_at: string;
    is_active: boolean;
}

interface OrganizationData {
    id: string;
    name: string;
    slug: string;
    member_count: number;
    subscription_tier: string;
    billing_email: string;
}

const Organization: React.FC = () => {
    const [organization, setOrganization] = useState<OrganizationData | null>(null);
    const [members, setMembers] = useState<OrganizationMember[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [showInviteModal, setShowInviteModal] = useState(false);
    const [inviteEmail, setInviteEmail] = useState('');
    const [inviteRole, setInviteRole] = useState<'member' | 'viewer'>('member');

    useEffect(() => {
        fetchOrganization();
        fetchMembers();
    }, []);

    const fetchOrganization = async () => {
        try {
            // TODO: Replace with actual API call
            setOrganization({
                id: '1',
                name: 'Acme Corporation',
                slug: 'acme-corp',
                member_count: 12,
                subscription_tier: 'pro',
                billing_email: 'billing@acme.com',
            });
        } catch (err) {
            setError(getErrorMessage(err));
        }
    };

    const fetchMembers = async () => {
        try {
            setLoading(true);
            // TODO: Replace with actual API call
            setMembers([
                {
                    id: '1',
                    email: 'john@acme.com',
                    full_name: 'John Doe',
                    role: 'owner',
                    joined_at: '2024-01-15',
                    is_active: true,
                },
                {
                    id: '2',
                    email: 'jane@acme.com',
                    full_name: 'Jane Smith',
                    role: 'admin',
                    joined_at: '2024-02-20',
                    is_active: true,
                },
                {
                    id: '3',
                    email: 'bob@acme.com',
                    full_name: 'Bob Johnson',
                    role: 'member',
                    joined_at: '2024-03-10',
                    is_active: true,
                },
            ]);
            setError(null);
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setLoading(false);
        }
    };

    const handleInvite = async () => {
        try {
            // TODO: API call to invite member
            console.log('Inviting:', inviteEmail, inviteRole);
            setShowInviteModal(false);
            setInviteEmail('');
            await fetchMembers();
        } catch (err) {
            setError(getErrorMessage(err));
        }
    };

    const getRoleIcon = (role: string) => {
        switch (role) {
            case 'owner':
                return <Crown className="w-4 h-4 text-yellow-600" />;
            case 'admin':
                return <Shield className="w-4 h-4 text-blue-600" />;
            case 'viewer':
                return <Eye className="w-4 h-4 text-gray-600" />;
            default:
                return <Users className="w-4 h-4 text-green-600" />;
        }
    };

    const getRoleBadgeColor = (role: string) => {
        switch (role) {
            case 'owner':
                return 'bg-yellow-100 text-yellow-800';
            case 'admin':
                return 'bg-blue-100 text-blue-800';
            case 'viewer':
                return 'bg-gray-100 text-gray-800';
            default:
                return 'bg-green-100 text-green-800';
        }
    };

    return (
        <div className="min-h-screen bg-gray-50 p-6">
            <div className="max-w-6xl mx-auto">
                {/* Header */}
                <div className="mb-8">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-3">
                            <Building2 className="w-8 h-8 text-green-600" />
                            <div>
                                <h1 className="text-3xl font-bold text-gray-900">
                                    {organization?.name || 'Organization'}
                                </h1>
                                <p className="text-gray-600 mt-1">
                                    Manage your team and organization settings
                                </p>
                            </div>
                        </div>
                        <button
                            onClick={() => setShowInviteModal(true)}
                            className="flex items-center space-x-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
                        >
                            <UserPlus className="w-5 h-5" />
                            <span>Invite Member</span>
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

                {/* Organization Info */}
                {organization && (
                    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-lg font-semibold text-gray-900">Organization Details</h2>
                            <button className="flex items-center space-x-2 text-gray-600 hover:text-gray-900">
                                <Settings className="w-5 h-5" />
                                <span>Settings</span>
                            </button>
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                            <div>
                                <span className="text-sm text-gray-500">Organization ID</span>
                                <p className="text-gray-900 font-medium">{organization.slug}</p>
                            </div>
                            <div>
                                <span className="text-sm text-gray-500">Members</span>
                                <p className="text-gray-900 font-medium">{organization.member_count}</p>
                            </div>
                            <div>
                                <span className="text-sm text-gray-500">Plan</span>
                                <p className="text-gray-900 font-medium capitalize">{organization.subscription_tier}</p>
                            </div>
                            <div>
                                <span className="text-sm text-gray-500">Billing Email</span>
                                <p className="text-gray-900 font-medium">{organization.billing_email}</p>
                            </div>
                        </div>
                    </div>
                )}

                {/* Members List */}
                <div className="bg-white rounded-xl shadow-sm border border-gray-200">
                    <div className="p-4 border-b border-gray-200 flex items-center justify-between">
                        <h2 className="text-lg font-semibold text-gray-900">Team Members</h2>
                        <button
                            onClick={fetchMembers}
                            className="p-2 hover:bg-gray-100 rounded-lg"
                        >
                            <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
                        </button>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead className="bg-gray-50">
                                <tr>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                                        Member
                                    </th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                                        Role
                                    </th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                                        Joined
                                    </th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                                        Actions
                                    </th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-200">
                                {loading ? (
                                    <tr>
                                        <td colSpan={4} className="px-6 py-8 text-center">
                                            <RefreshCw className="w-6 h-6 animate-spin mx-auto text-green-600" />
                                        </td>
                                    </tr>
                                ) : members.length === 0 ? (
                                    <tr>
                                        <td colSpan={4} className="px-6 py-8 text-center text-gray-500">
                                            No members found
                                        </td>
                                    </tr>
                                ) : (
                                    members.map((member) => (
                                        <tr key={member.id}>
                                            <td className="px-6 py-4">
                                                <div>
                                                    <div className="text-sm font-medium text-gray-900">
                                                        {member.full_name || 'No name'}
                                                    </div>
                                                    <div className="text-sm text-gray-500">{member.email}</div>
                                                </div>
                                            </td>
                                            <td className="px-6 py-4">
                                                <span
                                                    className={`inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-semibold ${getRoleBadgeColor(
                                                        member.role
                                                    )}`}
                                                >
                                                    {getRoleIcon(member.role)}
                                                    <span className="capitalize">{member.role}</span>
                                                </span>
                                            </td>
                                            <td className="px-6 py-4 text-sm text-gray-500">
                                                {new Date(member.joined_at).toLocaleDateString()}
                                            </td>
                                            <td className="px-6 py-4">
                                                {member.role !== 'owner' && (
                                                    <button
                                                        className="text-red-600 hover:text-red-700"
                                                        title="Remove member"
                                                    >
                                                        <Trash2 className="w-5 h-5" />
                                                    </button>
                                                )}
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* Invite Modal */}
                {showInviteModal && (
                    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                        <div className="bg-white rounded-xl shadow-xl p-6 max-w-md w-full mx-4">
                            <h3 className="text-lg font-semibold text-gray-900 mb-4">Invite Team Member</h3>
                            <div className="space-y-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Email Address
                                    </label>
                                    <input
                                        type="email"
                                        value={inviteEmail}
                                        onChange={(e) => setInviteEmail(e.target.value)}
                                        placeholder="colleague@example.com"
                                        className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">Role</label>
                                    <select
                                        value={inviteRole}
                                        onChange={(e) => setInviteRole(e.target.value as 'member' | 'viewer')}
                                        className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                                    >
                                        <option value="member">Member</option>
                                        <option value="viewer">Viewer</option>
                                    </select>
                                </div>
                            </div>
                            <div className="flex justify-end space-x-3 mt-6">
                                <button
                                    onClick={() => {
                                        setShowInviteModal(false);
                                        setInviteEmail('');
                                    }}
                                    className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={handleInvite}
                                    disabled={!inviteEmail}
                                    className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    Send Invitation
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default Organization;
