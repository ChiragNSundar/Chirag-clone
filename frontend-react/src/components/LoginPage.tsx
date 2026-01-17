import { useState } from 'react';
import { motion } from 'framer-motion';
import { Chrome, Github, Loader2, Shield, AlertCircle } from 'lucide-react';
import clsx from 'clsx';

interface LoginPageProps {
    onLoginSuccess?: () => void;
}

interface OAuthStatus {
    google: boolean;
    github: boolean;
}

/**
 * LoginPage - OAuth2 Social Login
 */
export function LoginPage({ onLoginSuccess }: LoginPageProps) {
    const [isLoading, setIsLoading] = useState<'google' | 'github' | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [oauthStatus, setOauthStatus] = useState<OAuthStatus | null>(null);

    // Check OAuth status on mount
    useState(() => {
        fetch('/api/auth/status')
            .then((res) => res.json())
            .then(setOauthStatus)
            .catch(() => setOauthStatus({ google: false, github: false }));

        // Check for token in URL (callback)
        const params = new URLSearchParams(window.location.search);
        const token = params.get('token');
        if (token) {
            localStorage.setItem('auth_token', token);
            onLoginSuccess?.();
        }
    });

    const handleGoogleLogin = async () => {
        if (isLoading || !oauthStatus?.google) return;

        setIsLoading('google');
        setError(null);

        try {
            const redirectUri = `${window.location.origin}/auth/callback/google`;
            const response = await fetch(`/api/auth/google/url?redirect_uri=${encodeURIComponent(redirectUri)}`);
            const data = await response.json();

            if (data.url) {
                // Store state for CSRF verification
                if (data.state) {
                    localStorage.setItem('oauth_state', data.state);
                }
                window.location.href = data.url;
            } else {
                setError('Failed to initiate Google login');
                setIsLoading(null);
            }
        } catch (err) {
            setError('Failed to connect to server');
            setIsLoading(null);
        }
    };

    const handleGithubLogin = async () => {
        if (isLoading || !oauthStatus?.github) return;

        setIsLoading('github');
        setError(null);

        try {
            const redirectUri = `${window.location.origin}/auth/callback/github`;
            const response = await fetch(`/api/auth/github/url?redirect_uri=${encodeURIComponent(redirectUri)}`);
            const data = await response.json();

            if (data.url) {
                if (data.state) {
                    localStorage.setItem('oauth_state', data.state);
                }
                window.location.href = data.url;
            } else {
                setError('Failed to initiate GitHub login');
                setIsLoading(null);
            }
        } catch (err) {
            setError('Failed to connect to server');
            setIsLoading(null);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-zinc-950 via-zinc-900 to-zinc-950 p-4">
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="w-full max-w-md"
            >
                {/* Logo/Header */}
                <div className="text-center mb-8">
                    <motion.div
                        initial={{ scale: 0.8 }}
                        animate={{ scale: 1 }}
                        transition={{ type: 'spring', stiffness: 200 }}
                        className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 mb-4"
                    >
                        <Shield className="w-8 h-8 text-white" />
                    </motion.div>
                    <h1 className="text-2xl font-bold text-white mb-2">Welcome Back</h1>
                    <p className="text-zinc-400">Sign in to access your digital twin</p>
                </div>

                {/* Login Card */}
                <div className="bg-zinc-900/50 backdrop-blur-xl border border-zinc-800 rounded-2xl p-6 space-y-4">
                    {/* Error Display */}
                    {error && (
                        <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm"
                        >
                            <AlertCircle size={16} />
                            {error}
                        </motion.div>
                    )}

                    {/* Google Login */}
                    <motion.button
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={handleGoogleLogin}
                        disabled={isLoading !== null || !oauthStatus?.google}
                        className={clsx(
                            'w-full flex items-center justify-center gap-3 px-4 py-3 rounded-xl font-medium transition-all',
                            oauthStatus?.google
                                ? 'bg-white text-zinc-900 hover:bg-zinc-100'
                                : 'bg-zinc-800 text-zinc-500 cursor-not-allowed'
                        )}
                    >
                        {isLoading === 'google' ? (
                            <Loader2 size={20} className="animate-spin" />
                        ) : (
                            <Chrome size={20} />
                        )}
                        {oauthStatus?.google ? 'Continue with Google' : 'Google not configured'}
                    </motion.button>

                    {/* GitHub Login */}
                    <motion.button
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={handleGithubLogin}
                        disabled={isLoading !== null || !oauthStatus?.github}
                        className={clsx(
                            'w-full flex items-center justify-center gap-3 px-4 py-3 rounded-xl font-medium transition-all',
                            oauthStatus?.github
                                ? 'bg-zinc-800 text-white hover:bg-zinc-700 border border-zinc-700'
                                : 'bg-zinc-800/50 text-zinc-500 cursor-not-allowed border border-zinc-800'
                        )}
                    >
                        {isLoading === 'github' ? (
                            <Loader2 size={20} className="animate-spin" />
                        ) : (
                            <Github size={20} />
                        )}
                        {oauthStatus?.github ? 'Continue with GitHub' : 'GitHub not configured'}
                    </motion.button>

                    {/* Divider */}
                    <div className="relative py-4">
                        <div className="absolute inset-0 flex items-center">
                            <div className="w-full border-t border-zinc-800" />
                        </div>
                        <div className="relative flex justify-center">
                            <span className="px-3 bg-zinc-900/50 text-zinc-500 text-sm">or</span>
                        </div>
                    </div>

                    {/* Legacy PIN Login (fallback) */}
                    <p className="text-center text-sm text-zinc-500">
                        Don't have an account?{' '}
                        <a href="/training" className="text-purple-400 hover:text-purple-300">
                            Use PIN access
                        </a>
                    </p>
                </div>

                {/* Footer */}
                <p className="text-center text-xs text-zinc-600 mt-6">
                    By signing in, you agree to our Terms of Service and Privacy Policy
                </p>
            </motion.div>
        </div>
    );
}

export default LoginPage;
