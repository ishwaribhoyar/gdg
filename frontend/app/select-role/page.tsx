'use client';

import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { api } from '@/lib/api';
import toast from 'react-hot-toast';
import { Building2, Users, ArrowRight, Loader2 } from 'lucide-react';

function SelectRoleContent() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const redirect = searchParams.get('redirect') || '/dashboard';

    const [selectedRole, setSelectedRole] = useState<'department' | 'college' | null>(null);
    const [loading, setLoading] = useState(false);
    const [checkingRole, setCheckingRole] = useState(true);

    // Check if user already has a role
    useEffect(() => {
        const checkExistingRole = async () => {
            try {
                const token = localStorage.getItem('auth_token');
                if (!token) {
                    window.location.href = '/login';
                    return;
                }

                const response = await api.get('/users/profile', {
                    headers: { Authorization: `Bearer ${token}` }
                });

                if (response.data.role) {
                    // User already has role - redirect to dashboard (hard refresh)
                    window.location.href = redirect;
                    return;
                }
            } catch (error) {
                console.error('Error checking role:', error);
            } finally {
                setCheckingRole(false);
            }
        };

        checkExistingRole();
    }, [router, redirect]);

    const handleSubmit = async () => {
        if (!selectedRole) {
            toast.error('Please select a user type');
            return;
        }

        setLoading(true);

        try {
            const token = localStorage.getItem('auth_token');
            if (!token) {
                window.location.href = '/login';
                return;
            }

            await api.post('/users/set-role', { role: selectedRole }, {
                headers: { Authorization: `Bearer ${token}` }
            });

            // Update stored user with role
            const storedUser = localStorage.getItem('auth_user');
            if (storedUser) {
                const user = JSON.parse(storedUser);
                user.role = selectedRole;
                localStorage.setItem('auth_user', JSON.stringify(user));
            }

            toast.success('Account setup complete!');

            // Redirect to role-specific dashboard (hard refresh to update auth state)
            if (selectedRole === 'college') {
                window.location.href = '/'; // College users go to main dashboard
            } else if (selectedRole === 'department') {
                window.location.href = '/nba-dashboard'; // Department users go to NBA dashboard
            } else {
                window.location.href = '/dashboard'; // Fallback
            }
        } catch (error: any) {
            console.error('Set role error:', error);
            toast.error(error.response?.data?.detail || 'Failed to set user type');
        } finally {
            setLoading(false);
        }
    };

    if (checkingRole) {
        return (
            <div className="min-h-screen bg-gradient-to-br from-primary-50 via-white to-secondary-50 flex items-center justify-center">
                <div className="animate-spin rounded-full h-12 w-12 border-3 border-primary border-t-transparent" />
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gradient-to-br from-primary-50 via-white to-secondary-50 flex items-center justify-center p-4">
            <div className="max-w-lg w-full bg-white rounded-3xl shadow-soft-xl p-8 border border-gray-100">
                {/* Header */}
                <div className="text-center mb-8">
                    <h1 className="text-3xl font-bold text-gray-800 mb-2">
                        Welcome to Smart Approval <span className="text-primary">AI</span>
                    </h1>
                    <p className="text-gray-600">Select your user type to continue</p>
                </div>

                {/* Role Selection Cards */}
                <div className="space-y-4 mb-8">
                    <button
                        type="button"
                        onClick={() => setSelectedRole('department')}
                        className={`w-full p-6 border-2 rounded-2xl transition-all flex items-start gap-4 text-left ${selectedRole === 'department'
                            ? 'border-primary bg-primary-50 ring-2 ring-primary/20'
                            : 'border-gray-200 bg-white hover:border-primary/50 hover:bg-gray-50'
                            }`}
                    >
                        <div className={`p-3 rounded-xl ${selectedRole === 'department' ? 'bg-primary text-white' : 'bg-gray-100 text-gray-600'
                            }`}>
                            <Users className="w-6 h-6" />
                        </div>
                        <div className="flex-1">
                            <h3 className={`font-semibold text-lg ${selectedRole === 'department' ? 'text-primary' : 'text-gray-800'
                                }`}>
                                Department User
                            </h3>
                            <p className="text-gray-500 text-sm mt-1">
                                Upload documents and view department-specific AICTE/NBA evaluations
                            </p>
                            <ul className="text-xs text-gray-400 mt-2 space-y-1">
                                <li>• Upload department evidence</li>
                                <li>• View department scores</li>
                                <li>• Access department dashboard</li>
                            </ul>
                        </div>
                    </button>

                    <button
                        type="button"
                        onClick={() => setSelectedRole('college')}
                        className={`w-full p-6 border-2 rounded-2xl transition-all flex items-start gap-4 text-left ${selectedRole === 'college'
                            ? 'border-primary bg-primary-50 ring-2 ring-primary/20'
                            : 'border-gray-200 bg-white hover:border-primary/50 hover:bg-gray-50'
                            }`}
                    >
                        <div className={`p-3 rounded-xl ${selectedRole === 'college' ? 'bg-primary text-white' : 'bg-gray-100 text-gray-600'
                            }`}>
                            <Building2 className="w-6 h-6" />
                        </div>
                        <div className="flex-1">
                            <h3 className={`font-semibold text-lg ${selectedRole === 'college' ? 'text-primary' : 'text-gray-800'
                                }`}>
                                College User
                            </h3>
                            <p className="text-gray-500 text-sm mt-1">
                                View all departments, comparisons, and institution-wide reports
                            </p>
                            <ul className="text-xs text-gray-400 mt-2 space-y-1">
                                <li>• Access all departments</li>
                                <li>• Compare department scores</li>
                                <li>• View trends & analytics</li>
                            </ul>
                        </div>
                    </button>
                </div>

                {/* Submit Button */}
                <button
                    onClick={handleSubmit}
                    disabled={!selectedRole || loading}
                    className="w-full bg-primary text-white py-4 rounded-xl font-semibold hover:bg-primary-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                    {loading ? (
                        <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                        <>
                            Continue
                            <ArrowRight className="w-5 h-5" />
                        </>
                    )}
                </button>

                <p className="text-center text-xs text-gray-400 mt-4">
                    This selection is permanent and cannot be changed later
                </p>
            </div>
        </div>
    );
}

export default function SelectRolePage() {
    return (
        <Suspense fallback={
            <div className="min-h-screen bg-gradient-to-br from-primary-50 via-white to-secondary-50 flex items-center justify-center">
                <div className="animate-spin rounded-full h-12 w-12 border-3 border-primary border-t-transparent" />
            </div>
        }>
            <SelectRoleContent />
        </Suspense>
    );
}
